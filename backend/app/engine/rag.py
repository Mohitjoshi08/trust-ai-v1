"""
Trace.ai — RAG Query Builder
Phase 4 Implementation
"""
from typing import List, Tuple
import logging
from datetime import datetime
from app.models.schemas import DecompositionResult, SegmentContribution, LogDocument

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
) -> Tuple[List[LogDocument], int, str]:
    """
    Strict-budget RAG retrieval with similarity-score-based tier expansion.

    Tier 1 (±24h): Retrieve logs within a tight window. If the top documents
    have similarity_score >= 0.7, accept them immediately.

    Tier 2 (±72h): If Tier 1 fails the threshold, expand the window but
    strictly raise the similarity threshold to >= 0.85 so only hyper-relevant
    logs survive — preventing LLM token bloat and hallucinations.

    Returns (logs, final_time_buffer_hours, retrieval_path).
    """
    from app.vectorstore.search import search_logs

    TIER1_WINDOW = 24          # ±24 hours
    TIER1_THRESHOLD = -10.0      # highly permissive for L2 distance
    TIER2_WINDOW = 72          # ±72 hours (expanded)
    TIER2_THRESHOLD = -10.0     # highly permissive for L2 distance

    # ── Tier 1: tight window ──────────────────────────────────────
    logger.info(f"RAG Tier 1: searching ±{TIER1_WINDOW}h with threshold={TIER1_THRESHOLD}")
    tier1_logs = await search_logs(
        dataset_id, query, start_time, end_time,
        time_buffer_hours=TIER1_WINDOW
    )

    # Check if top documents meet the quality bar
    if tier1_logs:
        top_score = max(log.similarity_score for log in tier1_logs)
        qualified_logs = [log for log in tier1_logs if log.similarity_score >= TIER1_THRESHOLD]

        if qualified_logs:
            retrieval_path = (
                f"Tier 1 accepted: {len(qualified_logs)} logs within ±{TIER1_WINDOW}h "
                f"(top score {top_score:.2f} >= {TIER1_THRESHOLD})"
            )
            logger.info(retrieval_path)
            return qualified_logs, TIER1_WINDOW, retrieval_path

        logger.info(
            f"Tier 1 insufficient: top score {top_score:.2f} < {TIER1_THRESHOLD}. "
            f"Expanding to Tier 2."
        )

    # ── Tier 2: expanded window, stricter threshold ───────────────
    logger.info(f"RAG Tier 2: searching ±{TIER2_WINDOW}h with threshold={TIER2_THRESHOLD}")
    tier2_logs = await search_logs(
        dataset_id, query, start_time, end_time,
        time_buffer_hours=TIER2_WINDOW
    )

    if tier2_logs:
        qualified_logs = [log for log in tier2_logs if log.similarity_score >= TIER2_THRESHOLD]

        if qualified_logs:
            retrieval_path = (
                f"Expanded to ±{TIER2_WINDOW}h due to insufficient ±{TIER1_WINDOW}h results. "
                f"{len(qualified_logs)} hyper-relevant logs passed threshold {TIER2_THRESHOLD}."
            )
            logger.info(retrieval_path)
            return qualified_logs, TIER2_WINDOW, retrieval_path

    # ── Fallback: return whatever we have ─────────────────────────
    fallback_logs = tier2_logs if tier2_logs else (tier1_logs if tier1_logs else [])
    retrieval_path = (
        f"Expanded to ±{TIER2_WINDOW}h but no logs met threshold {TIER2_THRESHOLD}. "
        f"Returning {len(fallback_logs)} best-effort logs."
    )
    logger.warning(retrieval_path)
    return fallback_logs, TIER2_WINDOW, retrieval_path
