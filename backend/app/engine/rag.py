"""
Trace.ai — RAG Query Builder
Phase 4 Implementation
"""
from typing import List
from app.models.schemas import DecompositionResult, SegmentContribution

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
