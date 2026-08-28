---

# Trace.ai — PRD Step 2: Deterministic Metric Decomposition (v2)
**The Mathematical Drill-Down That Isolates the Culprit Segment**

---

## 1. Overview

### 1.1 What This Step Does
When Step 1 detects an aggregate anomaly (e.g., "total daily revenue dropped 35.2% between Aug 5-7"), this step answers the immediate follow-up: **where exactly did the drop come from?** It deterministically decomposes the aggregate metric across every available dimension (region, device, channel, etc.) to find the specific segment responsible.

### 1.2 Why This Step Exists
An aggregate anomaly is not actionable. "Revenue dropped" tells a VP nothing. "Revenue dropped **because iOS conversion fell 65%**" tells them exactly which team to call. This step transforms a vague alert into a precise, dimensionally-specific diagnosis — without invoking any AI.

### 1.3 Position in the Pipeline
```
[Step 1: BSTS Anomaly Detection]
        ↓
[Step 2: Metric Decomposition] ← YOU ARE HERE
        ↓
[Step 3: Time-Bounded RAG]
        ↓
[Step 4: Hypothesis Engine]
```

### 1.4 Key Principle
**No LLM is involved in this step.** This is pure deterministic arithmetic — pandas groupby operations, volume delta calculations, and contribution scoring. The math is auditable and reproducible.

---

## 2. Mathematical Definition & Ambiguity Rules

### 2.1 Delta & Contribution Formula

For any segment $i$ within a dimension $D$:
1. Baseline Mean ($\bar{y}_{i, \text{base}}$): Average hourly/daily metric value over the 30 days preceding the anomaly start.
2. Anomaly Mean ($\bar{y}_{i, \text{anomaly}}$): Average metric value during the anomaly window.
3. Absolute Delta ($\Delta y_i$):
   $$\Delta y_i = \bar{y}_{i, \text{anomaly}} - \bar{y}_{i, \text{base}}$$
4. Absolute Total Drop Volume ($\Delta Y_{\text{drop}}$): Sum of all negative deltas across segments in dimension $D$:
   $$\Delta Y_{\text{drop}} = \sum_{k: \Delta y_k < 0} |\Delta y_k|$$
5. Contribution Score ($C_i$):
   $$C_i = \begin{cases} \frac{|\Delta y_i|}{\Delta Y_{\text{drop}}} & \text{if } \Delta y_i < 0 \\ 0 & \text{if } \Delta y_i \ge 0 \end{cases}$$

This ensures:
- $C_i \in [0.0, 1.0]$ for all segments.
- Segments with positive deltas (growth) get $C_i = 0$ (they didn't cause the drop).
- $\sum_{i} C_i = 1.0$ across all failing segments.

### 2.2 Ambiguity Threshold Formula

Let $C_{(1)}$ and $C_{(2)}$ be the top two contribution scores in dimension $D$:

$$\text{is\_ambiguous} = \begin{cases} \text{True} & \text{if } (C_{(1)} - C_{(2)}) < 0.15 \\ \text{False} & \text{if } (C_{(1)} - C_{(2)}) \ge 0.15 \end{cases}$$

> **Interpretation:** If the top contributor accounts for less than 15 percentage points more drop volume than the second contributor (e.g., Driver A = 48%, Driver B = 44%), the system flags the decomposition as **ambiguous** and passes both drivers to Step 3.

---

## 3. Scope

### 3.1 In Scope
| Item | Detail |
|------|--------|
| Dimension-wise metric decomposition | Group by each dimension, compute $C_i$ and % change |
| Level 1 & Level 2 multi-level drill-down | Level 1 (by dimension) → Level 2 (cross-dimension sub-segment) |
| Explicit Level 2 refinement rules | Refine driver to Level 2 sub-segment iff sub-contribution > 80% |
| Ambiguous decomposition handling | Explicit 15% delta threshold ($C_{(1)} - C_{(2)} < 0.15$) |
| Reconciled Metric Naming | `aggregate_deviation_pct` (-35.2%) vs `segment_percent_change` (-65.0%) |

---

## 4. Input Contract (From Step 1)

```python
AnomalyWindow(
    start_time=datetime(2025, 8, 5, 2, 0, 0),
    end_time=datetime(2025, 8, 7, 9, 0, 0),
    severity=3.2,
    direction="drop",
    metric_name="revenue",
    aggregate_actual_mean=29150.00,
    aggregate_expected_mean=45000.00,
    aggregate_deviation_pct=-35.2,
    detection_method=DetectionMethod.BSTS
)
```

---

## 5. Multi-Level Drill-Down Algorithm

### 5.1 Level 1 vs Level 2 Execution Rules

```
Step 1: Compute Level 1 contributions for each single dimension (Region, Device).
        → Rank dimensions by max segment contribution C_(1).
        → Top dimension: Device (iOS C_iOS = 0.95, Android C_Android = 0.00, Web C_Web = 0.05).
        → Device is un-ambiguous (0.95 - 0.05 = 0.90 >= 0.15).

Step 2: Drill into Level 2 for the top Level 1 segment(s).
        → If Level 1 is un-ambiguous: calculate Level 2 sub-contributions for primary_driver (e.g. Device=iOS x Region).
        → If Level 1 is ambiguous (is_ambiguous == True): calculate Level 2 sub-contributions for BOTH primary_driver and secondary_driver to provide dual drill-down trees.
        → Sub-contributions within iOS: NA = 33%, EMEA = 34%, APAC = 33%.

Step 3: Level 2 Refinement Decision Rule:
        IF max Level 2 sub-contribution > 0.80:
            Refine primary_driver to (Level 1 + Level 2 sub-segment)
            drill_down_path = ["revenue", "device=iOS", "region=EMEA"]
        ELSE:
            Retain primary_driver at Level 1 (device=iOS)
            mark Level 2 status as "uniform_across_subsegments"
            drill_down_path = ["revenue", "device=iOS"]
```

> **Why this resolves ambiguity:** If iOS is broken everywhere equally (33/34/33), the root cause is a global iOS bug, not a regional iOS CDN issue. Level 2 explicitly verifies whether the drop is isolated to a sub-segment or uniform across sub-segments.

---

## 6. Pydantic Schemas & API Endpoints

```python
class SegmentContribution(BaseModel):
    dimension: str                # e.g., "device"
    segment_value: str            # e.g., "iOS"
    baseline_mean: float          # $15,200/day
    anomaly_mean: float           # $5,320/day
    absolute_change: float        # -$9,880/day
    segment_percent_change: float # -65.0% (isolated segment drop)
    contribution_to_total: float  # 0.95 (95% of total drop volume)

class Level2DrillDown(BaseModel):
    parent_segment: str           # "device=iOS"
    sub_dimension: str            # "region"
    is_uniform: bool              # True (33%/34%/33%)
    dominant_subsegment: Optional[str] # None unless sub-contribution > 0.80

class DecompositionResult(BaseModel):
    anomaly_window: AnomalyWindow
    primary_driver: SegmentContribution
    secondary_driver: Optional[SegmentContribution]
    is_ambiguous: bool            # True iff (C1 - C2) < 0.15
    level2_drilldown: Level2DrillDown
    all_segments: List[SegmentContribution]
    drill_down_path: List[str]    # ["revenue", "device=iOS"]
```

### `POST /api/v1/analyze/decompose`

**Response Example:**
```json
{
  "anomaly_window": {
    "aggregate_deviation_pct": -35.2
  },
  "primary_driver": {
    "dimension": "device",
    "segment_value": "iOS",
    "segment_percent_change": -65.0,
    "contribution_to_total": 0.95
  },
  "secondary_driver": null,
  "is_ambiguous": false,
  "level2_drilldown": {
    "parent_segment": "device=iOS",
    "sub_dimension": "region",
    "is_uniform": true,
    "dominant_subsegment": null
  },
  "drill_down_path": ["revenue", "device=iOS"]
}
```

---

## 7. Testing Requirements

| Test Category | Test Case | Assertion |
|---------------|-----------|-----------|
| Standard Scenario | iOS 65% drop, Android flat | `primary_driver.segment_value == "iOS"`, `is_ambiguous == False` |
| Ambiguity Formula | iOS drop 50%, EMEA drop 48% ($|C_1 - C_2| = 0.04 < 0.15$) | `is_ambiguous == True`, `secondary_driver` populated |
| Level 2 Non-Uniform | iOS drop concentrated 90% in NA | `drill_down_path == ["revenue", "device=iOS", "region=NA"]` |
| Level 2 Uniform | iOS drop split 33/34/33 across regions | `level2_drilldown.is_uniform == True`, driver remains `device=iOS` |
| Positive Segment Delta | Android revenue +15% during anomaly | `C_Android == 0.0`, handled without error |
