"""
Trace.ai — Deterministic Metric Decomposer
Phase 3 Implementation
"""
import pandas as pd
from typing import List, Tuple, Dict, Any
from app.models.schemas import (
    AnomalyWindow, DecompositionResult, SegmentContribution, Level2DrillDown
)

def _calculate_segment_contribution(
    segment_df: pd.DataFrame,
    baseline_start: pd.Timestamp,
    anomaly_start: pd.Timestamp,
    anomaly_end: pd.Timestamp,
    metric_col: str,
    total_aggregate_delta: float,
    global_anomaly_len: int,
    dimension: str,
    segment_value: str
) -> SegmentContribution:
    
    baseline_data = segment_df[(segment_df.index >= baseline_start) & (segment_df.index < anomaly_start)]
    anomaly_data = segment_df[(segment_df.index >= anomaly_start) & (segment_df.index <= anomaly_end)]
    
    baseline_mean = float(baseline_data[metric_col].mean()) if not baseline_data.empty else 0.0
    anomaly_mean = float(anomaly_data[metric_col].mean()) if not anomaly_data.empty else 0.0
    
    absolute_change = anomaly_mean - baseline_mean
    segment_percent_change = (absolute_change / baseline_mean * 100) if baseline_mean != 0 else 0.0
    
    weight = len(anomaly_data) / global_anomaly_len if global_anomaly_len > 0 else 0.0
    weighted_absolute_change = absolute_change * weight
    
    contribution_amount = absolute_change
    contribution_share_of_aggregate = (weighted_absolute_change / total_aggregate_delta * 100) if total_aggregate_delta != 0 else 0.0
    
    return SegmentContribution(
        dimension=dimension,
        segment_value=str(segment_value),
        baseline_mean=baseline_mean,
        anomaly_mean=anomaly_mean,
        absolute_change=absolute_change,
        segment_percent_change=segment_percent_change,
        contribution_amount=contribution_amount,
        contribution_share_of_aggregate=contribution_share_of_aggregate,
        contribution_to_total=contribution_share_of_aggregate
    )

def run_decomposition(
    df: pd.DataFrame, 
    anomaly: AnomalyWindow,
    metric_col: str = "metric_value",
    dimensions: List[str] = ["region", "device"]
) -> DecompositionResult:
    """
    Decompose the metric anomaly across specified dimensions.
    """
    # 1. Prepare data
    work = df.copy()
    if 'timestamp' in work.columns:
        work['timestamp'] = pd.to_datetime(work['timestamp'])
        work = work.set_index('timestamp')
    else:
        # Assuming index is timestamp if 'timestamp' column is not found
        work.index = pd.to_datetime(work.index)
        
    anomaly_start = pd.to_datetime(anomaly.start_time)
    anomaly_end = pd.to_datetime(anomaly.end_time)
    baseline_start = anomaly_start - pd.Timedelta(days=30)
    
    # Global delta
    global_baseline = work[(work.index >= baseline_start) & (work.index < anomaly_start)]
    global_anomaly = work[(work.index >= anomaly_start) & (work.index <= anomaly_end)]
    
    global_baseline_mean = float(global_baseline[metric_col].mean()) if not global_baseline.empty else 0.0
    global_anomaly_mean = float(global_anomaly[metric_col].mean()) if not global_anomaly.empty else 0.0
    total_aggregate_delta = global_anomaly_mean - global_baseline_mean
    
    if total_aggregate_delta == 0:
        total_aggregate_delta = 1e-9 # Prevent division by zero
    
    all_segments: List[SegmentContribution] = []
    
    # 2. Iterate through each dimension and calculate segment contributions
    for dim in dimensions:
        if dim not in work.columns:
            continue
            
        groups = work.groupby(dim)
        for val, group_df in groups:
            seg_contrib = _calculate_segment_contribution(
                segment_df=group_df,
                baseline_start=baseline_start,
                anomaly_start=anomaly_start,
                anomaly_end=anomaly_end,
                metric_col=metric_col,
                total_aggregate_delta=total_aggregate_delta,
                dimension=dim,
                segment_value=val
            )
            all_segments.append(seg_contrib)
            
    # Sort segments by absolute contribution share (magnitude)
    all_segments.sort(key=lambda x: abs(x.contribution_share_of_aggregate), reverse=True)
    
    if not all_segments:
        # Fallback if no dimensions or no data
        dummy = SegmentContribution(
            dimension="none", segment_value="none", baseline_mean=0, anomaly_mean=0,
            absolute_change=0, segment_percent_change=0, contribution_amount=0, contribution_share_of_aggregate=0, contribution_to_total=0
        )
        return DecompositionResult(
            anomaly_window=anomaly,
            primary_driver=dummy,
            secondary_driver=None,
            is_ambiguous=False,
            level2_drilldowns=[],
            all_segments=[],
            drill_down_paths=[]
        )
        
    primary_driver = all_segments[0]
    secondary_driver = all_segments[1] if len(all_segments) > 1 else None
    
    # Ambiguity check
    is_ambiguous = False
    if secondary_driver:
        # If top two contributors are within 15% of each other
        diff = abs(abs(primary_driver.contribution_share_of_aggregate) - abs(secondary_driver.contribution_share_of_aggregate))
        if diff <= 15.0:
            is_ambiguous = True

    # Build drill-down path
    drill_down_paths = [["Total", f"{primary_driver.dimension}={primary_driver.segment_value}"]]
    if is_ambiguous and secondary_driver:
        drill_down_paths.append(["Total", f"{secondary_driver.dimension}={secondary_driver.segment_value}"])
        
    # Level 2 Drilldown (for primary driver)
    level2_drilldowns = []
    other_dims = [d for d in dimensions if d != primary_driver.dimension]
    if other_dims:
        sub_dim = other_dims[0]
        # Filter work df to primary driver
        primary_df = work[work[primary_driver.dimension] == primary_driver.segment_value]
        
        sub_groups = primary_df.groupby(sub_dim)
        sub_contribs = []
        for sub_val, sub_group_df in sub_groups:
            sub_contrib = _calculate_segment_contribution(
                segment_df=sub_group_df,
                baseline_start=baseline_start,
                anomaly_start=anomaly_start,
                anomaly_end=anomaly_end,
                metric_col=metric_col,
                total_aggregate_delta=primary_driver.absolute_change if primary_driver.absolute_change != 0 else 1e-9, 
                dimension=sub_dim,
                segment_value=f"{sub_val}"
            )
            sub_contribs.append(sub_contrib)
            
        sub_contribs.sort(key=lambda x: abs(x.contribution_share_of_aggregate), reverse=True)
        dominant_sub = sub_contribs[0].segment_value if sub_contribs else None
        
        # Determine if uniform
        is_uniform = True
        if len(sub_contribs) > 1:
            diff = abs(abs(sub_contribs[0].contribution_share_of_aggregate) - abs(sub_contribs[1].contribution_share_of_aggregate))
            if diff > 30.0:
                is_uniform = False
                
        level2 = Level2DrillDown(
            parent_segment=primary_driver.segment_value,
            sub_dimension=sub_dim,
            is_uniform=is_uniform,
            dominant_subsegment=dominant_sub,
            sub_contributions=sub_contribs
        )
        level2_drilldowns.append(level2)

    return DecompositionResult(
        anomaly_window=anomaly,
        primary_driver=primary_driver,
        secondary_driver=secondary_driver if is_ambiguous else None,
        is_ambiguous=is_ambiguous,
        level2_drilldowns=level2_drilldowns,
        all_segments=all_segments,
        drill_down_paths=drill_down_paths
    )
