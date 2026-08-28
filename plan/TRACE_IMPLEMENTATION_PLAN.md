# Trace.ai — Implementation Plan for Antigravity

## Objective

Upgrade the current Trace.ai MVP from a simple anomaly → decomposition → RAG → single-hypothesis flow into a more defensible **evidence-backed KPI investigation engine**.

The goal is **not** to add random AI features. The goal is to strengthen the existing product against the main logical weaknesses:

1. Correlation must not be presented as proven causation.
2. Confidence must be explainable rather than a misleading probability.
3. Competing explanations should be compared explicitly.
4. Evidence must be traceable to the final explanation.
5. Time-bounded retrieval must be able to expand when evidence is insufficient.
6. The system should use recovery/after-event evidence when available.
7. KPI decomposition must reconcile to the aggregate movement.
8. Ambiguous cases must be surfaced instead of forcing a winner.

The current repository already contains:

- BSTS-based anomaly detection.
- Deterministic metric decomposition.
- Time-bounded semantic retrieval over synthetic operational logs.
- Gemini-based hypothesis generation.
- Evidence IDs.
- Basic ambiguity handling.
- Golden-path cached outputs.
- A React frontend showing anomaly, decomposition, RAG evidence, hypothesis, confidence, and recommendation.

Build on these components. Do not rewrite the project unnecessarily.

---

# 1. Product Positioning Rules

The implementation and UI must use the following language consistently:

### Use
- `likely cause`
- `evidence strength`
- `supporting evidence`
- `competing hypotheses`
- `recommended next step`
- `investigate further`
- `ambiguous`
- `evidence-backed hypothesis`
- `converging evidence`

### Do NOT use
- `proven root cause`
- `causal proof`
- `92% probability of causation`
- `guaranteed root cause`
- `automatically fixes the incident`

The existing `confidence_score` may remain as an internal ranking score, but the UI must not imply that it is a calibrated probability.

---

# 2. Feature Priority

Implement in this order:

## P0 — Must Have

1. Evidence matrix / evidence checklist.
2. Multi-hypothesis comparison.
3. Evidence lineage / traceability.
4. Evidence-strength classification.
5. Adaptive retrieval windows.
6. Recovery validation.
7. Contribution reconciliation.
8. Ambiguity handling that can produce multiple hypotheses.

## P1 — Strongly Recommended

9. Investigation timeline.
10. Counterfactual / expected-signature checks.
11. Executive summary + analyst detail views.
12. Red-herring rejection display.
13. Reconciliation warnings when segment contributions do not explain aggregate movement.

## P2 — Optional

14. Analyst feedback on whether the hypothesis was correct.
15. Follow-up questions such as “Why?”, “What evidence?”, “What alternatives were rejected?”, “What should I investigate next?”

Do not build unnecessary integrations or autonomous remediation.

---

# 3. New Investigation Model

The canonical Trace pipeline should become:

```text
KPI anomaly
    ↓
1. DETECT
    ↓
2. DECOMPOSE
    ↓
3. GATHER EVIDENCE
    ↓
4. GENERATE + SCORE MULTIPLE HYPOTHESES
    ↓
5. VALIDATE AGAINST EVIDENCE
    ↓
6. DECIDE
    ├── HIGH EVIDENCE → recommend next action
    ├── MEDIUM EVIDENCE → investigate / verify
    └── AMBIGUOUS → show competing causes
```

Important: the LLM should not be the only source of truth. Deterministic evidence checks should contribute to the final evidence strength.

---

# 4. P0 — Multi-Hypothesis Engine

## Current behavior

`backend/app/engine/hypothesis.py` currently prompts Gemini to return hypotheses, but the frontend primarily treats the first hypothesis as the main result.

## Required behavior

Generate or maintain **2–3 competing hypotheses** whenever the retrieved evidence supports more than one plausible explanation.

A hypothesis should contain:

```python
class Hypothesis(BaseModel):
    rank: int
    cause_title: str
    evidence_strength: str   # HIGH / MEDIUM / LOW / INSUFFICIENT
    evidence_score: int      # 0-100 internal score; NOT a probability
    reasoning: str
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str]
    evidence_checks: List[EvidenceCheck]
    recommended_action: str
    status: str              # recommended / investigate / rejected / ambiguous
```

Add:

```python
class EvidenceCheck(BaseModel):
    check_name: str
    result: str               # pass / fail / unknown
    explanation: str
    weight: float
```

Suggested checks:

- temporal_alignment
- affected_segment_match
- symptom_match
- operational_confirmation
- recovery_validation
- aggregate_reconciliation
- contradiction_found

The engine may use rules to generate candidate hypotheses from retrieved logs and then ask Gemini to synthesize/reason over them.

Do not allow Gemini to invent evidence IDs. Only IDs present in the retrieved evidence may appear in `supporting_evidence_ids` or `contradicting_evidence_ids`.

---

# 5. P0 — Evidence Matrix

Create a deterministic evidence matrix for every hypothesis.

Example:

| Check | Stripe deployment | CDN issue | Seasonality |
|---|---:|---:|---:|
| Deployment before anomaly | PASS | UNKNOWN | FAIL |
| Affected segment matches | PASS | FAIL | UNKNOWN |
| Error signature matches | PASS | FAIL | UNKNOWN |
| Operational incident confirms | PASS | FAIL | UNKNOWN |
| Recovery after rollback | PASS | FAIL | UNKNOWN |

This must be computed from actual available evidence, not hallucinated by the LLM.

Expose the matrix through the API and frontend.

Recommended new response structure:

```python
class EvidenceMatrix(BaseModel):
    hypothesis_id: str
    checks: List[EvidenceCheck]
    passed_count: int
    failed_count: int
    unknown_count: int
```

The frontend should show this when the user expands a hypothesis.

---

# 6. P0 — Evidence Strength

Replace the current user-facing `92% CONFIDENCE` presentation.

Use:

### HIGH EVIDENCE
### MEDIUM EVIDENCE
### LOW EVIDENCE
### INSUFFICIENT EVIDENCE

Suggested deterministic mapping:

- HIGH: strong multi-signal support and no major contradiction.
- MEDIUM: several supporting checks but at least one unknown or weak link.
- LOW: weak or mostly indirect evidence.
- INSUFFICIENT: no reliable explanation.

Keep the numeric `evidence_score` internally for ranking/debugging, but explicitly document that it is **not a calibrated probability**.

If the existing `confidence_score` field is retained for backwards compatibility, rename its UI label to `Evidence score` and add a tooltip:

> “Evidence score reflects rule-based support across observed signals. It is not a causal probability.”

---

# 7. P0 — Evidence Lineage

Every conclusion must be traceable.

Add an API response structure like:

```python
class EvidenceLink(BaseModel):
    id: str
    timestamp: datetime
    source: str
    excerpt: str
    relevance_score: float
    role: str  # temporal / symptom / deployment / incident / recovery / contradiction
```

For each hypothesis, expose the evidence links behind the reasoning.

Frontend interaction:

```text
LIKELY CAUSE: Stripe SDK deployment

Why?
✓ PR #1847 preceded anomaly
✓ iOS checkout errors appeared
✓ BUG-2291 confirms incompatibility
✓ Revenue recovered after rollback

[View evidence]
```

Clicking `View evidence` should show the exact log excerpts and timestamps.

Never fabricate citations.

---

# 8. P0 — Adaptive Retrieval Windows

Current RAG logic uses fixed windows based on dimension.

Keep the existing dimension-specific windows as the first pass, but add fallback expansion.

Example:

```text
Pass 1: existing configured window
        ↓
Enough evidence? → YES → stop
        ↓ NO
Pass 2: expand to ±72 hours
        ↓
Enough evidence? → YES → stop
        ↓ NO
Pass 3: expand to ±7 days
        ↓
Enough evidence? → YES → stop
        ↓ NO
Return INSUFFICIENT EVIDENCE
```

Do not blindly expand if the current evidence is already strong.

The API should expose retrieval metadata:

```python
class RetrievalMetadata(BaseModel):
    initial_window_start: datetime
    initial_window_end: datetime
    final_window_start: datetime
    final_window_end: datetime
    expansion_steps: int
    evidence_sufficient: bool
```

This helps explain why a particular document was considered.

---

# 9. P0 — Recovery Validation

Use the existing planted recovery evidence in the synthetic logs.

Current planted sequence includes:

- PR #1847: Stripe SDK v12.3 deployment.
- iOS payment failure / `STRIPE_INIT_FAIL`.
- Jira `BUG-2291`.
- PR #1852: Stripe SDK rollback to v11.9 / hotfix.

Detect the pattern:

```text
change/deployment
        ↓
anomaly + symptom
        ↓
incident confirmation
        ↓
recovery action
        ↓
metric recovery
```

Add a recovery check:

```python
class RecoveryValidation(BaseModel):
    detected: bool
    recovery_event_id: Optional[str]
    recovery_event_timestamp: Optional[datetime]
    metric_recovered: bool
    recovery_summary: str
```

Important:

Do NOT call this “causal proof”.

Display it as:

> “Post-action recovery strengthens the hypothesis.”

If the metric does not recover, mark the recovery check as `FAIL` or `UNKNOWN` rather than forcing a positive result.

For demo data, use the existing recovery evidence. Do not invent a new fake metric recovery unless the current data requires augmentation.

---

# 10. P0 — Fix Contribution Logic

The current decomposition uses `contribution_to_total` within each dimension based on negative segment deltas.

Do not compare independent dimension-normalized contribution scores as if they were globally comparable.

Implement a reconciled contribution model.

For each dimension/segment, calculate:

```text
segment_delta = anomaly_period_mean - baseline_period_mean
```

Then calculate the contribution in **absolute KPI units** and percentage of the aggregate KPI delta.

Prefer a schema such as:

```python
class SegmentContribution(BaseModel):
    dimension: str
    segment_value: str
    baseline_mean: float
    anomaly_mean: float
    absolute_change: float
    segment_percent_change: float
    contribution_amount: float
    contribution_share_of_aggregate: float
```

Important:

If the metric is revenue, use currency impact rather than only normalized shares.

Example UI:

```text
TOTAL REVENUE LOSS: -$15,850

Device
  iOS      -$15,100   95.3%
  Web      -$750       4.7%
  Android   +$0        0.0%
```

Do NOT display “iOS caused 95.3% of the revenue drop” unless the reconciliation calculation actually supports that statement. Prefer:

> “iOS accounts for 95.3% of the reconciled aggregate decline.”

---

# 11. P0 — Reconciliation Check

Add an explicit check:

```python
class ReconciliationResult(BaseModel):
    aggregate_delta: float
    explained_delta: float
    residual_delta: float
    explained_share: float
    status: str  # reconciled / partial / failed
    tolerance: float
```

Use a configurable tolerance such as 5% of the absolute aggregate delta.

Example:

```text
Aggregate change:    -$15,850
Explained by drivers: -$15,120
Residual:              -$730
Explained share:        95.4%
Status:                 RECONCILED
```

If residual exceeds tolerance:

### DECOMPOSITION INCOMPLETE

The final hypothesis should be prevented from claiming high evidence strength when reconciliation is poor.

---

# 12. P1 — Investigation Timeline

Add a visual timeline to the frontend.

For the current demo scenario, the timeline should approximately communicate:

```text
Aug 4 23:45    PR #1847 — Stripe SDK v12.3 deployment
      ↓
Aug 5          Revenue anomaly begins
      ↓
Aug 5 09:30    Zendesk — iOS payment failure
      ↓
Aug 5 11:00    Slack — STRIPE_INIT_FAIL spike
      ↓
Aug 5 14:00    Jira BUG-2291 — P1 iOS checkout failure
      ↓
Aug 7 09:00    PR #1852 — Stripe SDK rollback
      ↓
Post-event     Recovery validation
```

Do not hardcode this timeline in the UI. Build it dynamically from the returned evidence and anomaly timestamps.

Sort chronologically.

Tag events by source with small badges.

---

# 13. P1 — Counterfactual / Expected-Signature Checks

For common hypothesis classes, define expected signatures.

Examples:

### Stripe/iOS deployment hypothesis
Expected:
- iOS affected disproportionately.
- Payment error signature appears.
- Deployment precedes anomaly.
- Checkout-related incident appears.
- Recovery after rollback/hotfix is plausible.

### CDN latency hypothesis
Expected:
- Affected region should dominate.
- Latency/availability evidence should align with the same region.
- Revenue impact should appear in region rather than only device.

### Seasonality hypothesis
Expected:
- Similar historical pattern at comparable dates/times.
- No unusual operational evidence.

Represent the checks as structured data.

Do not use an LLM to invent expected signatures dynamically in the first implementation. Start with deterministic rules for the demo.

---

# 14. P1 — Red-Herring Rejection

The synthetic dataset already contains adversarial/noise logs. Use them.

The UI should optionally show:

### Evidence considered

**Stripe SDK deployment** — SUPPORTS

**iOS checkout failure** — SUPPORTS

**BUG-2291** — SUPPORTS

**EMEA CDN latency** — DOES NOT MATCH PRIMARY DRIVER

**Android certificate task** — WRONG SEGMENT

**July iOS crash** — OUTSIDE INITIAL WINDOW

This is extremely important for the demo because it demonstrates that Trace is not simply matching keywords.

Add a small explanation for rejected evidence:

- wrong segment
- outside time window
- contradictory signal
- low relevance

---

# 15. P1 — Executive Summary + Analyst Detail

The frontend should have two levels of detail.

## Executive summary

Example:

> **Revenue fell 35.2%, primarily driven by iOS.**
> 
> The strongest explanation is an iOS checkout deployment that preceded `STRIPE_INIT_FAIL` errors and a P1 incident. Evidence strength: **HIGH**.
> 
> **Recommended next step:** Verify the rollback/hotfix and monitor checkout recovery.

## Analyst detail

Show:

- anomaly window
- statistical baseline
- aggregate change
- reconciled segment contributions
- timeline
- evidence matrix
- supporting/contradicting evidence
- competing hypotheses
- retrieval window used
- recovery validation
- recommendation

---

# 16. P2 — Analyst Feedback

Optional.

Allow the analyst to mark a hypothesis:

- Correct
- Incorrect
- Still investigating

Store the feedback locally for the MVP.

Data shape:

```python
class HypothesisFeedback(BaseModel):
    hypothesis_id: str
    verdict: str
    timestamp: datetime
    notes: str = ""
```

Do not build a full model-learning system yet.

---

# 17. P2 — Follow-Up Questions

Optional frontend capability.

After an investigation, expose buttons:

- Why do you believe this?
- What evidence supports it?
- What alternatives were rejected?
- What should I investigate next?
- What changed first?

These questions should be answered from structured investigation state and retrieved evidence, not from unconstrained LLM memory.

---

# 18. API Changes

Keep the existing `/api` contracts backwards compatible where practical.

Extend the report schema instead of breaking the existing frontend data model all at once.

Suggested top-level structure:

```python
class InvestigationReport(BaseModel):
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    reconciliation: ReconciliationResult
    rag: RAGResult
    retrieval_metadata: RetrievalMetadata
    timeline: List[EvidenceLink]
    hypotheses: List[Hypothesis]
    recovery_validation: Optional[RecoveryValidation]
    overall_status: str
```

If renaming existing fields would break too much code, retain compatibility aliases.

---

# 19. Frontend Changes

Update `frontend/src/App.tsx` and related CSS/components.

Target UI hierarchy:

```text
[ Executive KPI summary ]

Revenue ↓35.2%
Expected $45K/day → Actual $29.15K/day

[ Primary driver ]

iOS ↓65%

[ Investigation timeline ]

[ Hypothesis comparison ]

1. Stripe SDK deployment     HIGH EVIDENCE
2. CDN issue                 LOW EVIDENCE
3. Seasonality               REJECTED

[ Evidence matrix ]

[ Supporting evidence ]

[ Recovery validation ]

[ Recommended next step ]

[ Alternative / ambiguity warning ]
```

Avoid an overcomplicated dashboard. The visual hierarchy should tell the investigation story.

---

# 20. Demo Scenario Requirements

The golden demo should remain deterministic and reliable.

For the existing planted scenario, the final UI should ideally show:

### Detection
- Revenue anomaly around Aug 5–7, 2025.
- Aggregate drop around 35.2%.
- Expected revenue around $45,000/day.
- Actual anomaly-period revenue around $29,150/day.

### Decomposition
- iOS is the dominant device-level driver.
- iOS drop around 65%.

### Evidence
- PR #1847 / Stripe SDK v12.3.
- Zendesk payment failures.
- Slack `STRIPE_INIT_FAIL` spike.
- Jira `BUG-2291`.
- PR #1852 rollback/hotfix.
- Red herrings are explicitly down-ranked/rejected where appropriate.

### Final interpretation
Use wording like:

> **Likely cause: iOS checkout incompatibility introduced by Stripe SDK v12.3.**
>
> **Evidence strength: HIGH.**
>
> Supporting evidence includes temporal alignment, segment alignment, matching error signatures, incident confirmation, and post-action recovery evidence.
>
> **Recommended next step: verify the hotfix/rollback and monitor checkout recovery.**

Do not say “caused with 92% probability” or “causal proof.”

---

# 21. Ambiguous Demo Scenario

Create a second deterministic test case where two explanations have similar support.

The UI should show:

```text
AMBIGUOUS INVESTIGATION

Hypothesis A    48 evidence score
Hypothesis B    45 evidence score

No explanation dominates the evidence.

Trace recommendation:
DO NOT TAKE AN AUTOMATED ACTION.
Collect additional evidence / expand retrieval window.
```

The exact synthetic data can be simple. The objective is to prove that the product can say:

> “We do not have enough evidence to safely choose.”

This is a core differentiator.

---

# 22. Testing Requirements

Add/update tests for:

## Unit tests

### Anomaly
- normal seasonal movement is not falsely classified where existing tests permit.
- planted anomaly is detected.

### Decomposition
- contribution amounts reconcile to aggregate movement within tolerance.
- no global comparison of independently normalized dimension scores.
- primary driver is chosen by reconciled aggregate contribution.

### Retrieval
- initial retrieval window works.
- expansion occurs only when evidence is insufficient.
- final evidence list contains only logs in the final window.

### Evidence scoring
- each evidence check is deterministic.
- supporting evidence IDs exist in retrieved evidence.
- contradicted/irrelevant evidence cannot accidentally become supporting evidence.

### Hypothesis
- multiple hypotheses are preserved.
- ambiguous cases do not collapse to a single false winner.
- evidence strength is not treated as a probability.

### Recovery
- recovery event is identified where present.
- no recovery event results in `UNKNOWN`, not a fabricated PASS.

### API
- existing API consumers remain functional or receive compatibility fields.

---

# 23. Acceptance Criteria

The work is complete only when all of the following are true:

- [ ] Existing anomaly → decomposition → RAG → hypothesis flow still works.
- [ ] Demo remains deterministic with golden cache fallback.
- [ ] Primary and secondary hypotheses can be displayed.
- [ ] Evidence matrix is generated deterministically.
- [ ] Evidence can be traced back to exact source logs.
- [ ] User-facing confidence language is replaced by evidence-strength language.
- [ ] Contribution logic reconciles to the aggregate KPI movement.
- [ ] Reconciliation status is visible.
- [ ] Retrieval can expand when evidence is insufficient.
- [ ] Recovery evidence is used when available.
- [ ] Timeline is generated from actual evidence timestamps.
- [ ] Red-herring evidence is down-ranked/rejected with an explanation.
- [ ] Ambiguous cases produce an explicit ambiguity state.
- [ ] Recommended actions are presented as recommendations, not automatic fixes.
- [ ] No unsupported causal claims appear in the UI.
- [ ] No fabricated evidence IDs or source content are generated.
- [ ] Unit/API tests pass.
- [ ] Frontend builds successfully.
- [ ] The primary demo scenario remains visually convincing.

---

# 24. Non-Goals / Constraints

Do NOT:

- add unnecessary LLM agents.
- add real enterprise integrations for this MVP.
- introduce autonomous production remediation.
- claim statistical causal inference unless an actual causal method is implemented and validated.
- fabricate performance benchmarks.
- fabricate accuracy percentages.
- fabricate real-world customer data.
- replace the current architecture just for novelty.
- remove deterministic statistical checks in favor of LLM reasoning.

The current repository uses synthetic data. Keep that transparent in the product/demo.

---

# 25. Recommended Implementation Sequence

### Phase 1 — Data model and backend correctness

1. Add evidence-check / evidence-matrix schemas.
2. Add reconciliation schemas.
3. Fix decomposition contribution semantics.
4. Add evidence-strength computation.

### Phase 2 — Retrieval and investigation logic

5. Add adaptive retrieval windows.
6. Add recovery validation.
7. Add timeline generation.
8. Build competing-hypothesis support.
9. Add deterministic evidence checks.

### Phase 3 — Frontend

10. Replace confidence language.
11. Add executive summary.
12. Add hypothesis comparison.
13. Add evidence matrix.
14. Add evidence lineage.
15. Add timeline.
16. Add recovery validation.
17. Add ambiguity state.

### Phase 4 — Tests and hardening

18. Add unit tests.
19. Add an ambiguous synthetic scenario.
20. Test golden-cache and live/fallback paths.
21. Run frontend build.
22. Run backend tests.
23. Manually test the main demo end-to-end.

---

# 26. Final UX Story

The final product should make this story visually obvious:

```text
Revenue ↓35.2%
       ↓
Is this abnormal?
       ↓
YES — outside expected baseline
       ↓
Where is the impact?
       ↓
iOS is dominant driver
       ↓
What changed around it?
       ↓
PR #1847 / Stripe SDK v12.3
       ↓
What evidence supports that?
       ↓
Checkout failures + STRIPE_INIT_FAIL + BUG-2291
       ↓
Did recovery follow the remediation?
       ↓
Yes / No / Unknown
       ↓
Evidence strength
       ↓
HIGH / MEDIUM / LOW / AMBIGUOUS
       ↓
Next action
```

The product should feel like **an investigation engine**, not a chatbot answering questions about a dashboard.

---

# 27. Final Output Required from Antigravity

After implementing the changes:

1. Run backend tests.
2. Run frontend build.
3. Start the application.
4. Verify the primary demo scenario.
5. Verify the ambiguous scenario.
6. Check that no unsupported causal/probability claims remain in the UI.
7. Report files changed.
8. Report tests run and results.
9. Report any items intentionally left unimplemented.

Do not stop after writing code. Verify the complete user flow.
