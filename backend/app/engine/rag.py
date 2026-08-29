"""
Trace.ai — RAG Query Builder
Phase 4 Implementation
"""
from typing import List, Tuple
import logging
from datetime import datetime
from app.models.schemas import DecompositionResult, SegmentContribution, LogDocument, EvidenceStatus

logger = logging.getLogger(__name__)

QUERY_TEMPLATES = {
    "device": {
        "query": "{segment_value} app crash error failure checkout payment",
        "context": "platform-specific technical issue"
    },
    "region": {
        "query": "{segment_value} region outage latency CDN localization",
        "context": "regional infrastructure or localization issue"
    },
    "channel": {
        "query": "{segment_value} campaign traffic referral UTM acquisition",
        "context": "marketing or traffic source change"
    },
    "product": {
        "query": "{segment_value} product SKU inventory pricing stock",
        "context": "product-specific availability or pricing issue"
    },
    "_default": {
        "query": "{dimension} {segment_value} issue error failure anomaly",
        "context": "general operational issue"
    }
}

def build_rag_query_for_segment(segment: SegmentContribution, metric_name: str) -> str:
    template = QUERY_TEMPLATES.get(
        segment.dimension,
        QUERY_TEMPLATES["_default"]
    )
    query = template["query"].format(
        segment_value=segment.segment_value,
        dimension=segment.dimension,
        metric=metric_name
    )
    return query

def build_rag_queries(decomp: DecompositionResult) -> List[str]:
    """Returns multiple queries if decomposition is ambiguous."""
    metric_name = decomp.anomaly_window.metric_name
    queries = [build_rag_query_for_segment(decomp.primary_driver, metric_name)]
    
    if decomp.is_ambiguous and decomp.secondary_driver:
        queries.append(build_rag_query_for_segment(decomp.secondary_driver, metric_name))
        
    return queries

async def adaptive_search(
    dataset_id: str,
    query: str,
    start_time: datetime,
    end_time: datetime
) -> Tuple[List[LogDocument], int]:
    """
    Query ChromaDB with expanding time windows until conclusive evidence is found.
    Returns (logs, final_time_buffer_hours).
    """
    from app.vectorstore.search import search_logs
    from app.engine.hypothesis import evaluate_evidence
    
    windows = [24, 72, 168]  # 24 hours, 72 hours, 7 days
    
    for window in windows:
        logger.info(f"Trying RAG search with time_buffer_hours={window}")
        logs = await search_logs(dataset_id, query, start_time, end_time, time_buffer_hours=window)
        
        # Evaluate deterministic evidence strength
        anomaly_ts = str(start_time)
        evidence_items, _ = evaluate_evidence(anomaly_ts, logs)
        
        # If all checks return UNKNOWN, it means we found NO conclusive logs for deploy or error
        is_insufficient = all(item["status"] == EvidenceStatus.UNKNOWN for item in evidence_items)
        
        if not is_insufficient:
            logger.info(f"Conclusive evidence found at window={window}")
            return logs, window
            
    logger.warning(f"Reached max window ({windows[-1]}h) with insufficient evidence.")
    return logs, windows[-1]
