"""
Trace.ai — BSTS Anomaly Detection Engine
Written by: senior_ml_engineer
Reviewed by: principal_data_scientist

Implements Bayesian Structural Time Series anomaly detection with a
three-tier fallback strategy:
  1. BSTS with weekly seasonality
  2. BSTS without seasonality
  3. Scipy Z-score (mean ± sigma)

Public API:
  detect_anomalies(df) -> (List[TimeSeriesPoint], List[AnomalyWindow], DetectionMethod)
"""

import logging
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.structural import UnobservedComponents

from app.models.schemas import (
    AnomalyWindow, TimeSeriesPoint, DetectionMethod
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level BSTS fitting (exposed for monkeypatching in tests)
# ---------------------------------------------------------------------------

def fit_bsts_model(
    series: pd.Series,
    seasonal_period: int = 7
) -> Tuple[Optional[pd.DataFrame], DetectionMethod]:
    """
    Fit a BSTS model to a daily time-series and return a DataFrame with
    'expected', 'lower_bound', 'upper_bound' columns plus the detection
    method used.

    Returns (None, DetectionMethod.Z_SCORE) when all BSTS fits fail,
    signalling the caller to fall back to Z-score.
    """
    sigma_threshold = 2.0

    # Attempt 1: BSTS with weekly seasonality
    try:
        logger.info("Attempting BSTS with weekly seasonality (period=%d).", seasonal_period)
        model = UnobservedComponents(
            series,
            level='local linear trend',
            seasonal=seasonal_period,
            freq='D'
        )
        result = model.fit(disp=False)
        pred = result.get_prediction()

        out = pd.DataFrame(index=series.index)
        out['expected'] = pred.predicted_mean
        se = pred.se_mean
        out['lower_bound'] = out['expected'] - sigma_threshold * se
        out['upper_bound'] = out['expected'] + sigma_threshold * se
        return out, DetectionMethod.BSTS
    except Exception as e:
        logger.warning("BSTS with seasonality failed: %s. Trying without.", e)

    # Attempt 2: BSTS without seasonality
    try:
        model = UnobservedComponents(
            series,
            level='local linear trend',
            freq='D'
        )
        result = model.fit(disp=False)
        pred = result.get_prediction()

        out = pd.DataFrame(index=series.index)
        out['expected'] = pred.predicted_mean
        se = pred.se_mean
        out['lower_bound'] = out['expected'] - sigma_threshold * se
        out['upper_bound'] = out['expected'] + sigma_threshold * se
        return out, DetectionMethod.BSTS
    except Exception as e:
        logger.warning("BSTS without seasonality failed: %s. Falling back to Z-score.", e)

    return None, DetectionMethod.Z_SCORE


# ---------------------------------------------------------------------------
# Z-score fallback
# ---------------------------------------------------------------------------

def _zscore_bounds(series: pd.Series, sigma: float = 2.0) -> pd.DataFrame:
    """Simple mean ± sigma bounds."""
    mean_val = series.mean()
    std_val = series.std()
    # Guard: if std is 0 (constant series), set tiny std to avoid false anomalies
    if std_val == 0 or np.isnan(std_val):
        std_val = 1e-9

    out = pd.DataFrame(index=series.index)
    out['expected'] = mean_val
    out['lower_bound'] = mean_val - sigma * std_val
    out['upper_bound'] = mean_val + sigma * std_val
    return out


# ---------------------------------------------------------------------------
# Window detection
# ---------------------------------------------------------------------------

def _find_anomaly_windows(
    daily_df: pd.DataFrame,
    metric_col: str,
    detection_method: DetectionMethod
) -> List[AnomalyWindow]:
    """
    Group consecutive days where actual falls outside (lower, upper) bounds
    into AnomalyWindow objects.
    """
    windows: List[AnomalyWindow] = []

    actual = daily_df[metric_col]
    is_anomaly = (actual > daily_df['upper_bound']) | (actual < daily_df['lower_bound'])

    if not is_anomaly.any():
        return windows

    # Group consecutive anomaly days into blocks
    block_ids = (is_anomaly != is_anomaly.shift(1)).cumsum()
    anomaly_blocks = daily_df[is_anomaly].groupby(block_ids)

    for _, block in anomaly_blocks:
        start_time = block.index.min()
        end_time = block.index.max()
        actual_mean = float(block[metric_col].mean())
        expected_mean = float(block['expected'].mean())

        diff = actual_mean - expected_mean
        direction = "spike" if diff > 0 else "drop"

        if expected_mean != 0:
            deviation_pct = float(diff / expected_mean * 100)
        else:
            deviation_pct = 0.0

        abs_dev = abs(deviation_pct)

        # Filter out operationally insignificant deviations.
        # BSTS can produce very tight confidence bands on clean data,
        # causing sub-1% deviations to be flagged. A 5% minimum ensures
        # only meaningful KPI movements are surfaced.
        MIN_DEVIATION_PCT = 5.0
        if abs_dev < MIN_DEVIATION_PCT:
            continue

        if abs_dev > 50:
            severity = 3.0  # high
        elif abs_dev > 20:
            severity = 2.0  # medium
        else:
            severity = 1.0  # low

        windows.append(AnomalyWindow(
            start_time=start_time,
            end_time=end_time,
            severity=severity,
            direction=direction,
            metric_name=metric_col,
            aggregate_actual_mean=actual_mean,
            aggregate_expected_mean=expected_mean,
            aggregate_deviation_pct=round(deviation_pct, 2),
            detection_method=detection_method,
        ))

    return windows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_anomalies(
    df: pd.DataFrame,
    metric_col: str = "metric_value",
    timestamp_col: str = "timestamp",
) -> Tuple[List[TimeSeriesPoint], List[AnomalyWindow], DetectionMethod]:
    """
    Full anomaly-detection pipeline.

    Parameters
    ----------
    df : DataFrame with at least `timestamp_col` and `metric_col` columns.
    metric_col : name of the numeric metric column.
    timestamp_col : name of the timestamp column.

    Returns
    -------
    (time_series_points, anomaly_windows, detection_method)
    """
    if df.empty or metric_col not in df.columns:
        return [], [], DetectionMethod.Z_SCORE

    # Ensure datetime index for resampling
    work = df.copy()
    work[timestamp_col] = pd.to_datetime(work[timestamp_col])
    work = work.set_index(timestamp_col).sort_index()

    # Aggregate to daily (handles both hourly and already-daily data)
    daily = work[[metric_col]].resample('D').mean()
    daily[metric_col] = daily[metric_col].interpolate(method='linear')
    daily = daily.dropna(subset=[metric_col])

    if len(daily) < 7:
        logger.warning("Not enough data (%d days) for any model.", len(daily))
        return [], [], DetectionMethod.Z_SCORE

    # --- Fit model ---
    if len(daily) < 14:
        # Too few points for BSTS; go straight to Z-score
        logger.warning("Only %d days — using Z-score fallback.", len(daily))
        bounds_df = _zscore_bounds(daily[metric_col])
        method = DetectionMethod.Z_SCORE
    else:
        result, method = fit_bsts_model(daily[metric_col])
        if result is not None:
            bounds_df = result
        else:
            bounds_df = _zscore_bounds(daily[metric_col])
            method = DetectionMethod.Z_SCORE

    # Merge bounds into daily frame
    daily = daily.join(bounds_df)

    # --- Build TimeSeriesPoint list ---
    ts_points: List[TimeSeriesPoint] = []
    for ts, row in daily.iterrows():
        ts_points.append(TimeSeriesPoint(
            timestamp=ts,
            actual=float(row[metric_col]),
            predicted_mean=float(row['expected']),
            upper_bound=float(row['upper_bound']),
            lower_bound=float(row['lower_bound']),
        ))

    # --- Detect anomaly windows ---
    anomaly_windows = _find_anomaly_windows(daily, metric_col, method)

    return ts_points, anomaly_windows, method
