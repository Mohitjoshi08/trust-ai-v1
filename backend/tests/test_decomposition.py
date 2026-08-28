import pandas as pd
import pytest
from datetime import datetime
from app.models.schemas import AnomalyWindow, DetectionMethod
from app.engine.decomposition import calculate_contributions, run_decomposition

@pytest.fixture
def sample_df():
    # 30 days of baseline, 3 days of anomaly
    dates = pd.date_range(start="2025-07-06", end="2025-08-07 23:59:59", freq='h')
    
    data = []
    for dt in dates:
        is_anom = dt >= pd.Timestamp("2025-08-05")
        
        # Setup iOS to drop 500
        ios_val = 500 if is_anom else 1000
        android_val = 500
        web_val = 500
        
        data.extend([
            {"timestamp": dt, "device": "iOS", "region": "NA", "metric_value": ios_val},
            {"timestamp": dt, "device": "Android", "region": "EMEA", "metric_value": android_val},
            {"timestamp": dt, "device": "Web", "region": "APAC", "metric_value": web_val}
        ])
        
    return pd.DataFrame(data)

@pytest.fixture
def sample_window():
    return AnomalyWindow(
        start_time=datetime(2025, 8, 5),
        end_time=datetime(2025, 8, 7, 23, 59, 59),
        severity=3.0,
        direction="drop",
        metric_name="revenue",
        aggregate_actual_mean=1500,
        aggregate_expected_mean=2000,
        aggregate_deviation_pct=-25.0,
        detection_method=DetectionMethod.BSTS
    )

def test_decomposition(sample_df, sample_window):
    res = run_decomposition(sample_df, sample_window)
    
    assert res.primary_driver.dimension == "device"
    assert res.primary_driver.segment_value == "iOS"
    assert res.primary_driver.contribution_to_total == 1.0 # 100% of the drop
    assert res.primary_driver.segment_percent_change == -50.0
    
    assert res.is_ambiguous == False
    assert res.level2_drilldowns[0].is_uniform == False # 100% NA because only NA exists in fixture

def test_ambiguity(sample_df, sample_window):
    # iOS dropped by 500. Let's make Android drop by 480 (from 500 -> 20)
    sample_df.loc[(sample_df['timestamp'] >= '2025-08-05') & (sample_df['device'] == 'Android'), 'metric_value'] = 20
    
    res = run_decomposition(sample_df, sample_window)
    assert res.is_ambiguous == True
    
    # The primary driver could be either iOS (0.51) or NA (0.51) depending on sort order,
    # but the secondary driver in that same dimension will be 0.49, triggering ambiguity.
    assert (res.primary_driver.contribution_to_total - res.secondary_driver.contribution_to_total) < 0.15
