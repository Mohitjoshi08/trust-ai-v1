import pandas as pd
import numpy as np
from datetime import timedelta
from typing import List, Optional
from app.models.schemas import (
    AnomalyWindow, SegmentContribution, Level2DrillDown, DecompositionResult
)

def calculate_contributions(
    df: pd.DataFrame, 
    window: AnomalyWindow, 
    dimension: str
) -> List[SegmentContribution]:
    
    # 30 days prior baseline
    baseline_start = window.start_time - timedelta(days=30)
    baseline_end = window.start_time
    
    baseline_df = df[(df['timestamp'] >= baseline_start) & (df['timestamp'] < baseline_end)]
    anomaly_df = df[(df['timestamp'] >= window.start_time) & (df['timestamp'] <= window.end_time)]
    
    # Aggregate baseline means (daily average for fair comparison)
    # Since anomaly window is typically a few days, daily aggregation avoids day-of-week skew if anomaly is short, 
    # but the PRD specifies "average hourly/daily metric value". 
    # To keep it exact and simple, we'll just use the overall mean per hour since freq is hourly.
    
    base_means = baseline_df.groupby(dimension)['metric_value'].mean().to_dict()
    anom_means = anomaly_df.groupby(dimension)['metric_value'].mean().to_dict()
    
    segments = set(base_means.keys()).union(set(anom_means.keys()))
    
    results = []
    total_drop_volume = 0.0
    
    # First pass to compute absolute deltas and total drop volume
    for seg in segments:
        b_mean = base_means.get(seg, 0.0)
        a_mean = anom_means.get(seg, 0.0)
        delta = a_mean - b_mean
        if delta < 0:
            total_drop_volume += abs(delta)
            
    # Second pass to compute scores
    for seg in segments:
        b_mean = base_means.get(seg, 0.0)
        a_mean = anom_means.get(seg, 0.0)
        delta = a_mean - b_mean
        
        pct_change = (delta / b_mean * 100.0) if b_mean > 0 else 0.0
        
        contrib = 0.0
        if delta < 0 and total_drop_volume > 0:
            contrib = abs(delta) / total_drop_volume
            
        results.append(SegmentContribution(
            dimension=dimension,
            segment_value=seg,
            baseline_mean=round(b_mean, 2),
            anomaly_mean=round(a_mean, 2),
            absolute_change=round(delta, 2),
            segment_percent_change=round(pct_change, 2),
            contribution_to_total=round(contrib, 4)
        ))
        
    # Sort by contribution descending
    results.sort(key=lambda x: x.contribution_to_total, reverse=True)
    return results

def run_decomposition(df: pd.DataFrame, window: AnomalyWindow) -> DecompositionResult:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Strip timezones for safe comparison
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
    if window.start_time.tzinfo is not None:
        window.start_time = window.start_time.replace(tzinfo=None)
    if window.end_time.tzinfo is not None:
        window.end_time = window.end_time.replace(tzinfo=None)
    
    # Infer dimensions (all categorical columns except timestamp and metric_name/value)
    exclude_cols = {'timestamp', 'metric_name', 'metric_value'}
    dimensions = [c for c in df.columns if c not in exclude_cols]
    
    all_segments = []
    
    for dim in dimensions:
        segs = calculate_contributions(df, window, dim)
        all_segments.extend(segs)
        
    # Rank ALL Level 1 segments globally to find absolute top driver
    all_segments.sort(key=lambda x: x.contribution_to_total, reverse=True)
    
    primary = all_segments[0]
    
    # Secondary driver must be the next highest contributor WITHIN THE SAME DIMENSION
    same_dim_segments = [s for s in all_segments if s.dimension == primary.dimension]
    secondary = same_dim_segments[1] if len(same_dim_segments) > 1 else None
    
    is_ambiguous = False
    if secondary and (primary.contribution_to_total - secondary.contribution_to_total) < 0.15:
        is_ambiguous = True
        
    # Level 2 Drilldown
    drilldowns = []
    drill_down_paths = []
    
    drivers_to_drill = [primary]
    if is_ambiguous and secondary:
        drivers_to_drill.append(secondary)
        
    for driver in drivers_to_drill:
        # Filter df to only this segment
        driver_df = df[df[driver.dimension] == driver.segment_value]
        
        sub_dimensions = [d for d in dimensions if d != driver.dimension]
        
        for sub_dim in sub_dimensions:
            sub_segs = calculate_contributions(driver_df, window, sub_dim)
            if not sub_segs: continue
            
            top_sub = sub_segs[0]
            
            # Uniform definition: no sub-segment dominates heavily
            is_uniform = top_sub.contribution_to_total <= 0.50
            # Dominant definition: > 80%
            dominant_sub = top_sub.segment_value if top_sub.contribution_to_total > 0.80 else None
            
            path = ["revenue", f"{driver.dimension}={driver.segment_value}"]
            if dominant_sub:
                path.append(f"{sub_dim}={dominant_sub}")
                
            if path not in drill_down_paths:
                drill_down_paths.append(path)
            
            drilldowns.append(Level2DrillDown(
                parent_segment=f"{driver.dimension}={driver.segment_value}",
                sub_dimension=sub_dim,
                is_uniform=is_uniform,
                dominant_subsegment=dominant_sub,
                sub_contributions=sub_segs
            ))
            
    # Ensure at least the primary path exists if drilldown didn't yield refined paths
    if not any(f"{primary.dimension}={primary.segment_value}" in p[1] for p in drill_down_paths):
        drill_down_paths.append(["revenue", f"{primary.dimension}={primary.segment_value}"])
        
    if is_ambiguous and secondary and not any(f"{secondary.dimension}={secondary.segment_value}" in p[1] for p in drill_down_paths):
        drill_down_paths.append(["revenue", f"{secondary.dimension}={secondary.segment_value}"])

    return DecompositionResult(
        anomaly_window=window,
        primary_driver=primary,
        secondary_driver=secondary if secondary and secondary.contribution_to_total > 0.0 else None,
        is_ambiguous=is_ambiguous,
        level2_drilldowns=drilldowns,
        all_segments=all_segments,
        drill_down_paths=drill_down_paths
    )
