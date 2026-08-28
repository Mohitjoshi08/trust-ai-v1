"""
Trace.ai — BSTS Anomaly Detection Tests
Written by: senior_sdet
Reviewed by: director_of_qa

Validates the detect_anomalies() public API including:
  - Normal data → no anomalies
  - Planted drop → one anomaly detected
  - All-zero data → graceful handling
  - BSTS convergence failure → Z-score fallback
"""

import pandas as pd
import numpy as np
import pytest
from datetime import timedelta
from app.engine.bsts import detect_anomalies, fit_bsts_model
from app.models.schemas import DetectionMethod


def _generate_mock_data(start_date='2023-01-01', days=30, base_value=100.0):
    """Generate a simple daily DataFrame with a timestamp column and metric_value."""
    timestamps = [pd.to_datetime(start_date) + timedelta(days=i) for i in range(days)]
    values = [base_value] * days
    return pd.DataFrame({
        'timestamp': timestamps,
        'metric_value': values
    })


class TestNormalData:
    """Normal time-series with small noise should produce zero anomaly windows."""

    def test_normal_data_returns_empty_windows(self):
        df = _generate_mock_data(days=30, base_value=100.0)
        np.random.seed(42)
        df['metric_value'] += np.random.normal(0, 1, 30)

        points, windows, method = detect_anomalies(df)

        assert isinstance(points, list)
        assert len(windows) == 0, (
            f"Expected 0 anomaly windows, got {len(windows)}: "
            f"{[(str(w.start_time.date()), w.aggregate_deviation_pct) for w in windows]}"
        )
        assert method in (DetectionMethod.BSTS, DetectionMethod.Z_SCORE)


class TestPlantedAnomaly:
    """A massive planted drop should be detected as exactly one anomaly window."""

    def test_planted_drop_detected(self):
        df = _generate_mock_data(days=30, base_value=100.0)
        np.random.seed(42)
        df['metric_value'] += np.random.normal(0, 1, 30)

        # Plant a massive drop at day 20 (well after BSTS burn-in of ~7 days)
        df.loc[20, 'metric_value'] = 20.0

        points, windows, method = detect_anomalies(df)

        assert len(windows) >= 1, "Planted drop was not detected"
        # The first (or only) window should be a drop
        drop_windows = [w for w in windows if w.direction == "drop"]
        assert len(drop_windows) >= 1, f"No 'drop' windows found; directions = {[w.direction for w in windows]}"

        # Day 20 maps to 2023-01-21 (0-indexed start)
        target_date = pd.to_datetime('2023-01-21')
        matched = any(w.start_time <= target_date <= w.end_time for w in drop_windows)
        assert matched, f"Planted date 2023-01-21 not within any detected drop window"


class TestEdgeCases:
    """Edge cases: all-zero data, very short series."""

    def test_all_zero_data_handles_gracefully(self):
        df = _generate_mock_data(days=30, base_value=0.0)

        # Should not crash due to division by zero
        points, windows, method = detect_anomalies(df)
        # Constant zero series → no anomalies (std=0, guard prevents false positives)
        assert len(windows) == 0

    def test_too_short_series_returns_empty(self):
        df = _generate_mock_data(days=3, base_value=50.0)
        points, windows, method = detect_anomalies(df)
        assert len(points) == 0
        assert len(windows) == 0


class TestFallback:
    """When BSTS convergence fails, the engine must fall back to Z-score."""

    def test_convergence_failure_falls_back_to_zscore(self, monkeypatch):
        df = _generate_mock_data(days=30, base_value=100.0)
        np.random.seed(42)
        df['metric_value'] += np.random.normal(0, 1, 30)

        # Force fit_bsts_model to signal failure → Z-score fallback
        import app.engine.bsts as bsts_module

        def mock_fit_bsts(series, seasonal_period=7):
            return None, DetectionMethod.Z_SCORE

        monkeypatch.setattr(bsts_module, "fit_bsts_model", mock_fit_bsts)

        points, windows, method = detect_anomalies(df)
        assert method == DetectionMethod.Z_SCORE, f"Expected Z_SCORE fallback, got {method}"
