"""
Trace.ai — Decomposer Tests
"""

import pandas as pd
import numpy as np
import pytest
from datetime import datetime, timedelta
from app.engine.decomposer import run_decomposition
from app.models.schemas import AnomalyWindow, DetectionMethod

def _generate_mock_data(days=60, anomaly_drop=False, ambiguous=False):
    dates = pd.date_range(start='2025-07-01', periods=days*24, freq='h')
    
    data = []
    for dt in dates:
        for region in ['NA', 'EMEA', 'APAC']:
            for device in ['iOS', 'Android', 'Web']:
                # Base value
                val = 500.0 + np.random.normal(0, 50)
                
                # Planted anomaly for iOS between Aug 5 and Aug 7
                is_anomaly_window = (dt >= pd.to_datetime('2025-08-05 00:00:00')) and (dt < pd.to_datetime('2025-08-08 00:00:00'))
                
                if anomaly_drop and is_anomaly_window:
                    if ambiguous:
                        # Ambiguous: both iOS and NA drop similarly
                        if device == 'iOS':
                            val *= 0.65 # 35% drop
                        if region == 'NA':
                            val *= 0.60 # 40% drop
                    else:
                        # Clear driver: iOS drops
                        if device == 'iOS':
                            val *= 0.35 # 65% drop
                
                data.append({
                    'timestamp': dt,
                    'metric_name': 'revenue',
                    'metric_value': val,
                    'region': region,
                    'device': device
                })
                
    df = pd.DataFrame(data)
    return df

@pytest.fixture
def dummy_anomaly():
    return AnomalyWindow(
        start_time=datetime(2025, 8, 5),
        end_time=datetime(2025, 8, 7),
        severity=3.0,
        direction="drop",
        metric_name="revenue",
        aggregate_actual_mean=1000.0,
        aggregate_expected_mean=1500.0,
        aggregate_deviation_pct=-33.3,
        detection_method=DetectionMethod.BSTS
    )

def test_decomposer_clear_driver(dummy_anomaly):
    df = _generate_mock_data(anomaly_drop=True, ambiguous=False)
    result = run_decomposition(df, dummy_anomaly, metric_col="metric_value")
    
    assert result.primary_driver.segment_value == "iOS"
    assert result.primary_driver.contribution_share_of_aggregate > 75.0
    assert result.is_ambiguous == False

def test_decomposer_ambiguous(dummy_anomaly):
    df = _generate_mock_data(anomaly_drop=True, ambiguous=True)
    result = run_decomposition(df, dummy_anomaly, metric_col="metric_value")
    
    print([(s.dimension, s.segment_value, s.contribution_share_of_aggregate) for s in result.all_segments])
    assert result.is_ambiguous == True
    assert result.secondary_driver is not None

def test_decomposer_no_anomaly(dummy_anomaly):
    df = _generate_mock_data(anomaly_drop=False)
    result = run_decomposition(df, dummy_anomaly, metric_col="metric_value")
    
    # Since there's no real drop, the absolute changes are just noise
    # It shouldn't crash
    assert len(result.all_segments) > 0
