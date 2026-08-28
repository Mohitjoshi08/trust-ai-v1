---

# Trace.ai — PRD Step 4: Calibrated Hypothesis Engine (v2)
**The LLM Synthesis Layer — Constrained, Cited, and Calibrated**

---

## 1. Overview

### 1.1 What This Step Does
This is the final stage of the Trace.ai pipeline. It takes the mathematical evidence from Steps 1-2 (the anomaly window + the culprit segment) and the textual evidence from Step 3 (time-bounded operational logs) and feeds them to GPT-4o. The LLM evaluates whether the text logically explains the metric drop and outputs ranked hypotheses with confidence scores, cited evidence, and confidence-gated recommended actions.

### 1.2 Position in the Pipeline
```
[Step 1: BSTS Anomaly Detection]
        ↓
[Step 2: Metric Decomposition]
        ↓
[Step 3: Time-Bounded RAG]
        ↓
[Step 4: Hypothesis Engine] ← YOU ARE HERE
```

---

## 2. LLM Calibration Rubric & Confidence-Gating

### 2.1 Reconciled Calibration Rules

To eliminate calibration "dead zones," the scoring rubric explicitly maps all four score ranges to verifiable evidence conditions:

| Score Band | Condition Requirements | Meaning |
|------------|------------------------|---------|
| **90–100** | **3 of 3 Conditions:** (a) Deployment/code change logged *before* anomaly start, (b) user symptoms/tickets logged *during*, and (c) affected segment matches exactly. | Direct causal chain proven. |
| **70–89** | **2 of 3 Conditions:** e.g., Deployment before + segment match, but symptom logs are sparse; OR symptoms logged + segment match, but deployment commit is missing. | Strong probable cause. |
| **50–69** | **1 Condition + Secondary Correlation:** e.g., Only symptom logs exist for segment, with no code deployment or infrastructure ticket found. | Plausible operational issue. |
| **0–49** | **0 Conditions / Circumstantial:** Unrelated chatter, general latency logs without segment alignment. | Speculative / low confidence. |

### 2.2 Confidence-Gated `recommended_action`

To prevent false certainty where a low-confidence hypothesis prescribes an aggressive action (e.g. rolling back code based on a 30% guess):

- **If Confidence $\ge$ 70:** Output an **Actionable Fix** (e.g., *"Revert PR #1847 to Stripe SDK v11.9 immediately."*).
- **If Confidence < 50:** Output a **Diagnostic Action Only** (e.g., *"Do not roll back. Investigate Sentry error logs for iOS WebView policy changes before taking action."*).

---

## 3. Post-Processing & Hallucination Defense

### 3.1 Reasoning Alignment on Citation Stripping

If post-validation detects that the LLM cited an evidence ID that was not in the input set:
1. Strip the invalid ID from `supporting_evidence_ids`.
2. Append a warning string to `reasoning`: `"[Note: 1 uncited evidence reference removed during verification]"`
3. If zero valid citations remain: set `confidence_score_out_of_100 = min(score, 15)` and change `recommended_action` to a diagnostic recommendation.

```python
async def generate_hypotheses(...) -> HypothesisResponse:
    # ... call OpenAI API with response_format json_object ...
    raw = json.loads(response.choices[0].message.content)
    result = HypothesisResponse.model_validate(raw)

    valid_ids = {e.id for e in evidence}
    for hyp in result.hypotheses:
        original_count = len(hyp.supporting_evidence_ids)
        hyp.supporting_evidence_ids = [eid for eid in hyp.supporting_evidence_ids if eid in valid_ids]
        
        if len(hyp.supporting_evidence_ids) < original_count:
            hyp.reasoning += " [Citation notice: unverified evidence references were stripped]"
            
        if not hyp.supporting_evidence_ids:
            hyp.confidence_score_out_of_100 = min(hyp.confidence_score_out_of_100, 15)
            hyp.recommended_action = "Manual log review required. Unverified automated hypothesis."

    return result
```

---

## 4. API Response & Error Degradation Contract

> [!IMPORTANT]
> **No 500 / 502 Errors to Client:** The `POST /api/v1/analyze/root_cause` endpoint catches upstream timeouts or OpenAI failures internally and returns **HTTP 200 OK** with cached data or safe fallback states.

### `POST /api/v1/analyze/root_cause`

**Success Response (200 OK — Live Run):**
```json
{
  "hypotheses": [
    {
      "rank": 1,
      "cause_title": "Stripe SDK v12.3 Incompatibility with iOS 17.x WebView",
      "confidence_score_out_of_100": 92,
      "reasoning": "GitHub PR #1847 deployed a Stripe SDK upgrade on Aug 4 at 23:45, immediately preceding the anomaly window. Multiple Zendesk tickets confirm iOS checkout failures.",
      "supporting_evidence_ids": ["uuid-github-1847", "uuid-zendesk-4891"],
      "recommended_action": "Verify PR #1852 hotfix and roll back Stripe SDK to v11.9 on iOS."
    }
  ],
  "served_from": "live",
  "status": "healthy"
}
```

**Graceful Degradation Response (200 OK — OpenAI Service Timeout):**
```json
{
  "hypotheses": [
    {
      "rank": 1,
      "cause_title": "Stripe SDK v12.3 Incompatibility with iOS 17.x WebView",
      "confidence_score_out_of_100": 92,
      "reasoning": "Cached pipeline analysis served due to external API latency.",
      "supporting_evidence_ids": ["uuid-github-1847"],
      "recommended_action": "Verify PR #1852 hotfix."
    }
  ],
  "served_from": "cache",
  "status": "degraded_fallback"
}
```

---

## 5. Testing Requirements

| Test Category | Test Case | Expected Assertion |
|---------------|-----------|--------------------|
| Score Calibration | 3 conditions met (PR + tickets + iOS) | Score in 90-100 range |
| Score Calibration | Only symptom tickets, no deploy log | Score in 50-69 range |
| Confidence Gating | Hypothesis score = 35% | `recommended_action` starts with "Investigate" / "Do not execute..." |
| Citation Stripping | LLM invents ID "uuid-fake-99" | Stripped from list, warning appended to `reasoning` |
| Upstream Timeout | OpenAI call throws TimeoutException | API returns HTTP 200 OK with `served_from: "cache"` |
| Adversarial Logs | Red-herring EMEA log in input | Ranked hypothesis #1 remains Stripe SDK iOS |
