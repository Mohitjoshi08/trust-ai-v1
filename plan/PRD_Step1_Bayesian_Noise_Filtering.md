---

# Trace.ai — PRD Step 1: Bayesian Noise Filtering & Anomaly Detection (v2)
**The Statistical Baseline That Separates Signal From Noise**

---

## 1. Overview

### 1.1 What This Step Does
This is the first stage of the Trace.ai causal engine. It ingests raw time-series business metrics and uses Bayesian Structural Time Series (BSTS) modeling to build a probabilistic model of "normal" behavior. When actual data deviates beyond a dynamic confidence interval, the system flags an anomaly window — the precise time range where something went wrong.

### 1.2 Why This Step Exists
Business metrics fluctuate naturally. Revenue dips on weekends. Traffic spikes on campaign days. Without a statistical baseline, every small fluctuation would trigger an alert, creating **alert fatigue** — the #1 reason dashboards get ignored. This step ensures the system stays silent during normal noise and only fires when the data is genuinely abnormal.

### 1.3 Position in the Pipeline
```
[Step 1: BSTS Anomaly Detection] ← YOU ARE HERE
        ↓
[Step 2: Metric Decomposition]
        ↓
[Step 3: Time-Bounded RAG]
        ↓
[Step 4: Hypothesis Engine]
```

### 1.4 Key Principle
**No LLM is involved in this step.** This is pure deterministic statistics. The mathematical rigor of this step is what separates Trace.ai from "BI copilots" that dump data into GPT and hope for the best.

---

## 2. Scope

### 2.1 In Scope
| Item | Detail |
|------|--------|
| Synthetic data generation | 90-day hourly time-series (~65 days pre-anomaly baseline) |
| Synthetic log generation | 56+ operational logs with planted evidence & noise |
| BSTS model fitting | `statsmodels.UnobservedComponents` with convergence fallbacks |
| Anomaly detection | Dynamic confidence intervals with configurable σ threshold |
| Explicit detection method tagging | `detection_method` field in schema ("bsts", "z_score", "cached", "hardcoded") |
| Golden path cache | Pre-computed pipeline outputs for demo reliability |
| Project scaffolding | Full backend + frontend directory structure |

### 2.2 Out of Scope
| Item | Why |
|------|-----|
| Metric decomposition | Step 2 |
| Vector store / RAG | Step 3 |
| LLM hypothesis generation | Step 4 |
| Frontend visualization | Step 1 focuses on the engine; frontend is built in Steps 2-4 |
| Live data connectors | Hackathon uses synthetic data only |

---

## 3. Technical Architecture

### 3.1 Components Built in This Step

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry (skeleton)
│   ├── config.py                # Environment variables & settings
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # AnomalyWindow + TimeSeriesPoint models
│   ├── engine/
│   │   ├── __init__.py
│   │   └── bsts.py              # BSTS model + anomaly detection
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── golden_path.py       # CacheManager (demo/live toggle)
│   │   └── generate_cache.py    # Pipeline runner + cache writer
│   └── utils/
│       ├── __init__.py
│       └── time_utils.py        # Timestamp parsing & windowing
├── data/
│   ├── synthetic_metrics.csv    # Generated time-series data (90 days)
│   ├── synthetic_logs.json      # Generated operational logs
│   ├── generate_data.py         # Data generation script
│   └── golden_cache/
│       └── timeseries.json      # Cached BSTS output
├── tests/
│   ├── test_bsts.py
│   └── test_adversarial_data.py # Noisy/adversarial test cases
├── requirements.txt
└── .env.example
```

### 3.2 Mathematical Model

BSTS decomposes a time series into structural components:

$$y_t = \mu_t + \tau_t + \beta^T x_t + \epsilon_t$$

| Component | Symbol | Purpose |
|-----------|--------|---------|
| Local Linear Trend | μ_t | Captures slow upward/downward drift |
| Seasonal Component | τ_t | Captures repeating daily/weekly cycles (7-day period) |
| Regression | β^T x_t | (Not used in MVP — no external regressors) |
| Irregular / Noise | ε_t | Random noise the model expects |

The model calculates the **expected variance** (ε_t). If actual data falls within this expected noise band, the system stays silent. It only triggers when actual data breaches the confidence interval by >2σ.

---

## 4. Synthetic Data Specification

### 4.1 The Planted Scenario

> **The Story:** An e-commerce company's daily revenue drops sharply on **Tuesday Aug 5th** and doesn't recover until **Thursday Aug 7th**. The root cause is a broken checkout flow on the **iOS app** caused by a **bad deployment** pushed Monday night.

| Parameter | Value |
|-----------|-------|
| Metric | Daily Revenue ($) |
| Normal baseline | ~$45,000/day ± $3,000 noise |
| Anomaly period | Aug 5 – Aug 7, 2025 |
| Total aggregate drop magnitude | ~35.2% (total daily revenue falls from ~$45,000 to ~$29,150) |
| Segment drop magnitude | ~65.0% drop in iOS revenue specifically |
| Dimensions | `region` (NA, EMEA, APAC), `device` (iOS, Android, Web) |
| Root cause dimension | `device = iOS` only |

> [!NOTE]
> **Baseline History Resolution:** The total history spans **90 days** (June 1 – Aug 30, 2025). This provides **~65 days (~9.2 full weekly cycles)** of clean pre-anomaly baseline data, ensuring `statsmodels.UnobservedComponents` has sufficient training history to converge reliably on the 7-day weekly seasonality component ($\tau_t$).

### 4.2 Structured Metric Data — `synthetic_metrics.csv`

| Column | Type | Example |
|--------|------|---------|
| `timestamp` | ISO 8601 (hourly) | `2025-06-15T00:00:00Z` |
| `metric_name` | String | `revenue` |
| `metric_value` | Float | `1875.50` |
| `region` | String | `NA` / `EMEA` / `APAC` |
| `device` | String | `iOS` / `Android` / `Web` |

**Generation Logic:**
1. Generate **90 days** of hourly data (June 1 – Aug 30, 2025).
2. Base signal: sinusoidal daily pattern + weekly seasonality + Gaussian noise ($\sigma = 0.05 \cdot \mu$).
3. **Inject anomaly:** For `device=iOS` rows between Aug 5 02:00 and Aug 7 09:00, multiply `metric_value` by `0.35` (65% drop in iOS revenue).
4. Aggregate metric across all regions and devices drops by ~35.2% (since iOS represents ~54% of total baseline revenue).

### 4.3 Unstructured Operational Logs — `synthetic_logs.json`

| Field | Type | Example |
|-------|------|---------|
| `id` | UUID | `"a1b2c3d4..."` |
| `timestamp` | ISO 8601 | `"2025-08-04T23:45:00Z"` |
| `source` | String | `"GitHub"` / `"Zendesk"` / `"Jira"` / `"Slack"` |
| `text_content` | String | Full text of the event |

**Planted Evidence (within the anomaly window):**

| # | Timestamp | Source | Content |
|---|-----------|--------|---------|
| 1 | Aug 4, 11:45 PM | GitHub | `"Merged PR #1847: Refactored iOS checkout payment module. Updated Stripe SDK to v12.3. LGTM from @sarah."` |
| 2 | Aug 5, 9:30 AM | Zendesk | `"Ticket #4891: Customer reports 'Payment Failed' error on iPhone 14 Pro. Cannot complete purchase. Error code STRIPE_INIT_FAIL."` |
| 3 | Aug 5, 10:15 AM | Zendesk | `"Ticket #4903: 'Something went wrong' on checkout page. Using iPad Air, iOS 17.4. Was working yesterday."` |
| 4 | Aug 5, 11:00 AM | Slack | `"#incident-response: @oncall We're seeing a spike in iOS checkout errors. Sentry showing STRIPE_INIT_FAIL across iOS 17.x devices. Potentially related to last night's deploy?"` |
| 5 | Aug 5, 2:00 PM | Jira | `"BUG-2291: [P1 Critical] iOS Checkout Failure - Stripe SDK v12.3 incompatible with iOS 17.x WebView. Assigned: @dev-team."` |
| 6 | Aug 7, 9:00 AM | GitHub | `"Merged PR #1852: Hotfix - Reverted Stripe SDK to v11.9 for iOS. Fixes BUG-2291."` |

**Noise & Adversarial Red-Herring Logs:**
- Generate **~50 routine logs** across the 90 days.
- **Inject 3 Adversarial Logs:**
  - *Red Herring 1:* Aug 5, 10:00 AM (inside window): `"Slack #general: @channel EMEA CDN edge node experiencing 50ms latency elevation."` (Plausible-sounding region issue, but non-causal).
  - *Red Herring 2:* July 15 (outside window): `"Zendesk #3102: iOS app crash during checkout when switching languages."` (Historical iOS checkout log, outside time window).
  - *Red Herring 3:* Aug 6 (inside window): `"Jira TASK-4012: Update Android push notification certificate."` (Android issue inside window, non-causal).

---

## 5. BSTS Engine Implementation

### 5.1 Core Functions

| Function | Signature | Returns |
|----------|-----------|---------|
| `fit_bsts_model()` | `(series: pd.Series, seasonal_period: int = 7)` | Fitted model object |
| `get_predictions()` | `(model, steps: int)` | `{predicted_mean, lower_bound, upper_bound}` |
| `detect_anomalies()` | `(actual, predicted, upper, lower, sigma_threshold: float = 2.0)` | Tuple: `(List[AnomalyWindow], detection_method: str)` |

### 5.2 Pydantic Schemas

```python
from enum import Enum
from typing import List
from datetime import datetime
from pydantic import BaseModel

class DetectionMethod(str, Enum):
    BSTS = "bsts"
    Z_SCORE = "z_score"
    CACHED = "cached"
    HARDCODED = "hardcoded"

class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    actual: float
    predicted_mean: float
    upper_bound: float
    lower_bound: float

class AnomalyWindow(BaseModel):
    start_time: datetime
    end_time: datetime
    severity: float             # How many σ beyond the bound
    direction: str              # "drop" or "spike"
    metric_name: str
    aggregate_actual_mean: float  # Mean total revenue in window ($29,150)
    aggregate_expected_mean: float# Mean total revenue expected ($45,000)
    aggregate_deviation_pct: float# Percentage deviation of total aggregate (-35.2%)
    detection_method: DetectionMethod # Explicit metadata tag for transparency

class TimeSeriesResponse(BaseModel):
    data: List[TimeSeriesPoint]
    anomalies: List[AnomalyWindow]
    served_from: str            # "cache" or "live"
    detection_method: DetectionMethod
```

> [!IMPORTANT]
> **Reconciliation of Aggregate vs Segment Drop:**
> - `aggregate_deviation_pct` (-35.2%) measures the **total macro revenue drop** seen by Step 1.
> - In Step 2, `primary_driver.percent_change` (-65.0%) measures the **isolated segment drop** on iOS.
> Both values are explicitly named to prevent UI ambiguity.

### 5.3 Key Implementation Decisions
- Aggregate hourly total data to **daily sum** for the BSTS model (reduces high-frequency noise, speeds up convergence).
- Training window: first 65 days of data; test/forecast window: remaining 25 days.
- Anomaly criteria: `actual < lower_bound` (for drops) where `lower_bound = predicted_mean - (sigma_threshold * std_err)`.
- Merge consecutive anomalous daily points into contiguous `AnomalyWindow` objects.

### 5.4 Convergence & Fallback Strategy

| Attempt | Detection Method Tag | Algorithmic Implementation | When Used |
|---------|----------------------|----------------------------|-----------|
| 1 (Default) | `"bsts"` | `statsmodels.tsa.statespace.structural.UnobservedComponents` (Local Linear Trend + 7-day Seasonal) | Primary statistical engine |
| 2 | `"bsts"` | `UnobservedComponents` with Local Level (no seasonal component) | If Attempt 1 encounters NaN gradients |
| 3 | `"z_score"` | Rolling 14-day Gaussian window: `mean - 2.0 * std` | If State Space optimization fails to converge |
| 4 | `"hardcoded"` | Deterministic timestamp extraction (`Aug 5 02:00 - Aug 7 09:00`) | Emergency fallback for pitch environment |

> [!NOTE]
> Regardless of which attempt succeeds, `detection_method` is recorded in the response object. If a judge asks whether BSTS or z-score ran, the API response explicitly declares the active method.

---

## 6. Golden Path Cache

### 6.1 Why This Exists
Serves pre-computed, verified statistical outputs to ensure 100% deterministic demo execution while allowing live execution when `DEMO_MODE=false`.

### 6.2 Cache Structure (`data/golden_cache/timeseries.json`)

```json
{
  "data": [
    {
      "timestamp": "2025-06-01T00:00:00Z",
      "actual": 45230.00,
      "predicted_mean": 44800.00,
      "upper_bound": 49200.00,
      "lower_bound": 40400.00
    }
  ],
  "anomalies": [
    {
      "start_time": "2025-08-05T02:00:00Z",
      "end_time": "2025-08-07T09:00:00Z",
      "severity": 3.2,
      "direction": "drop",
      "metric_name": "revenue",
      "aggregate_actual_mean": 29150.00,
      "aggregate_expected_mean": 45000.00,
      "aggregate_deviation_pct": -35.2,
      "detection_method": "bsts"
    }
  ],
  "served_from": "cache",
  "detection_method": "cached"
}
```

---

## 7. API Endpoint

### `GET /api/v1/metrics/timeseries`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | query | `revenue` | Metric name |
| `start_date` | query | 90 days ago | Start of range |
| `end_date` | query | today | End of range |
| `granularity` | query | `daily` | `hourly` or `daily` |

**Success Response (200 OK):**
```json
{
  "data": [...],
  "anomalies": [{
    "start_time": "2025-08-05T02:00:00Z",
    "end_time": "2025-08-07T09:00:00Z",
    "severity": 3.2,
    "direction": "drop",
    "aggregate_deviation_pct": -35.2,
    "detection_method": "bsts"
  }],
  "served_from": "live",
  "detection_method": "bsts"
}
```

---

## 8. Testing Requirements

| Test Category | Test Case | Expected Assertion |
|---------------|-----------|--------------------|
| Baseline Model | 65-day clean baseline fit | `model.converged == True`, residuals mean ≈ 0 |
| Anomaly Detection | Planted Aug 5-7 drop | Detects exactly 1 window covering Aug 5-7 |
| Detection Method Tag | Live BSTS vs Fallback | `detection_method` matches actual algorithm executed |
| Adversarial: Noise | 1.2σ temporary dip | No anomaly window triggered (stays silent) |
| Adversarial: Zero Variance | Flat constant time series | Model handles without zero-division error |
| Cache Mode | `DEMO_MODE=true` | Returns pre-computed JSON in < 50ms |

---

## 9. Definition of Done

- [ ] `generate_data.py` creates 90-day dataset with planted anomaly and red-herring logs
- [ ] BSTS engine converges cleanly on the 65-day baseline
- [ ] `detection_method` is explicitly populated in schema and API responses
- [ ] `aggregate_deviation_pct` is clearly distinguished from segment drop
- [ ] All unit and adversarial tests pass
- [ ] Golden cache file generated and validated
