"""
Trace.ai — RAG Tests
"""
import pytest
from datetime import datetime
import asyncio
from app.models.schemas import AnomalyWindow, DecompositionResult, SegmentContribution, DetectionMethod
from app.engine.rag import build_rag_query_for_segment, build_rag_queries
from app.vectorstore.search import search_logs

# Just testing the query builder synchronously, and a mocked async test for search

def test_template_selection():
    seg_device = SegmentContribution(
        dimension="device", segment_value="iOS", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=1, contribution_to_total=1
    )
    q1 = build_rag_query_for_segment(seg_device, "revenue")
    assert "iOS" in q1
    assert "crash" in q1
    
    seg_region = SegmentContribution(
        dimension="region", segment_value="NA", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=1, contribution_to_total=1
    )
    q2 = build_rag_query_for_segment(seg_region, "revenue")
    assert "NA" in q2
    assert "latency" in q2
    
    seg_unknown = SegmentContribution(
        dimension="unknown_dim", segment_value="abc", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=1, contribution_to_total=1
    )
    q3 = build_rag_query_for_segment(seg_unknown, "revenue")
    assert "abc" in q3
    assert "anomaly" in q3

def test_ambiguous_decomp_queries():
    anomaly = AnomalyWindow(
        start_time=datetime(2025, 8, 5), end_time=datetime(2025, 8, 7),
        severity=3.0, direction="drop", metric_name="revenue",
        aggregate_actual_mean=100, aggregate_expected_mean=200, aggregate_deviation_pct=-50,
        detection_method=DetectionMethod.BSTS
    )
    seg1 = SegmentContribution(
        dimension="device", segment_value="iOS", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=50, contribution_to_total=50
    )
    seg2 = SegmentContribution(
        dimension="region", segment_value="NA", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=48, contribution_to_total=48
    )
    
    decomp = DecompositionResult(
        anomaly_window=anomaly,
        primary_driver=seg1,
        secondary_driver=seg2,
        is_ambiguous=True,
        level2_drilldowns=[],
        all_segments=[seg1, seg2],
        drill_down_paths=[]
    )
    
    queries = build_rag_queries(decomp)
    assert len(queries) == 2
    assert "iOS" in queries[0]
    assert "NA" in queries[1]

