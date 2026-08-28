---

# Trace.ai — PRD Step 3: Time-Bounded Agentic RAG (v2)
**The Evidence Retrieval Layer That Prevents Hallucination by Design**

---

## 1. Overview

### 1.1 What This Step Does
After Step 2 identifies the culprit segment (e.g., "device=iOS caused 95% of the revenue drop"), this step searches a vector database of unstructured operational logs — Zendesk tickets, GitHub commits, Jira bugs, Slack messages — to find **textual evidence** that might explain the anomaly. Crucially, it **only retrieves documents time-stamped within the anomaly window**, preventing the LLM in Step 4 from seeing irrelevant historical context.

### 1.2 Why This Step Exists
Standard RAG retrieves the "most similar" documents globally — which means a Zendesk ticket from 6 months ago about a similar (but unrelated) iOS bug could rank higher than last Tuesday's actual incident. Time-bounding the retrieval window is the critical differentiator that makes Trace.ai's hypotheses temporally grounded instead of historically confused.

### 1.3 Position in the Pipeline
```
[Step 1: BSTS Anomaly Detection]
        ↓
[Step 2: Metric Decomposition]
        ↓
[Step 3: Time-Bounded RAG] ← YOU ARE HERE
        ↓
[Step 4: Hypothesis Engine]
```

---

## 2. Dimension-Aware Query Templates & Time Buffers

To ensure the system generalizes beyond the single demo scenario, both **search queries** AND **pre-anomaly time buffers** are dimension-aware:

```python
QUERY_TEMPLATES = {
    "device": {
        "query": "{segment_value} app crash error failure checkout payment",
        "pre_buffer_hours": 24,   # Deploys usually happen within 24h of crash
        "post_buffer_hours": 2,
        "context": "platform-specific technical issue"
    },
    "region": {
        "query": "{segment_value} region outage latency CDN localization network provider",
        "pre_buffer_hours": 72,   # Infrastructure/CDN changes log up to 3 days prior
        "post_buffer_hours": 4,
        "context": "regional infrastructure or provider issue"
    },
    "channel": {
        "query": "{segment_value} campaign traffic referral UTM acquisition budget pause",
        "pre_buffer_hours": 48,   # Marketing campaign changes log 1-2 days prior
        "post_buffer_hours": 2,
        "context": "marketing or acquisition change"
    },
    "_default": {
        "query": "{dimension} {segment_value} issue error failure anomaly",
        "pre_buffer_hours": 24,
        "post_buffer_hours": 2,
        "context": "general operational issue"
    }
}

# Note on Semantic Generalization:
# sentence-transformers (all-MiniLM-L6-v2) maps natural language synonyms into dense vector space.
# Queries containing 'checkout payment failure' naturally match log text like 'payments broke' or
# 'transaction initialization error' with high cosine similarity (score > 0.78), ensuring retrieval
# generalizes beyond exact keyword overlap.
```

---

## 3. Time-Bounded Search & Ambiguity Quota Balancing

### 3.1 Search Logic with Balanced Quota

In standard execution, `search_logs()` retrieves the top-10 most relevant documents for the primary driver.

In **ambiguous mode** (where `decomp.is_ambiguous == True`), running two separate queries and merging solely by relevance score could introduce bias if Driver A has 9 docs and Driver B has 1 doc. To ensure **fair representation**:

```python
async def run_rag_pipeline(decomp: DecompositionResult) -> List[LogDocument]:
    if not decomp.is_ambiguous or not decomp.secondary_driver:
        # Standard Single Driver Mode: top-10 for primary query
        template = QUERY_TEMPLATES.get(decomp.primary_driver.dimension, QUERY_TEMPLATES["_default"])
        query = template["query"].format(
            segment_value=decomp.primary_driver.segment_value,
            dimension=decomp.primary_driver.dimension
        )
        return await search_logs(
            query=query,
            start_time=decomp.anomaly_window.start_time,
            end_time=decomp.anomaly_window.end_time,
            pre_buffer_hours=template["pre_buffer_hours"],
            post_buffer_hours=template["post_buffer_hours"],
            top_k=10
        )
    else:
        # Ambiguous Mode: Enforce strict 50/50 quota (Top-5 per driver)
        t1 = QUERY_TEMPLATES.get(decomp.primary_driver.dimension, QUERY_TEMPLATES["_default"])
        t2 = QUERY_TEMPLATES.get(decomp.secondary_driver.dimension, QUERY_TEMPLATES["_default"])
        
        q1 = t1["query"].format(segment_value=decomp.primary_driver.segment_value, dimension=decomp.primary_driver.dimension)
        q2 = t2["query"].format(segment_value=decomp.secondary_driver.segment_value, dimension=decomp.secondary_driver.dimension)
        
        res1 = await search_logs(q1, decomp.anomaly_window.start_time, decomp.anomaly_window.end_time, t1["pre_buffer_hours"], t1["post_buffer_hours"], top_k=5)
        res2 = await search_logs(q2, decomp.anomaly_window.start_time, decomp.anomaly_window.end_time, t2["pre_buffer_hours"], t2["post_buffer_hours"], top_k=5)
        
        # Interleave to present balanced evidence to Step 4 LLM
        balanced = []
        for d1, d2 in zip_longest(res1, res2):
            if d1: balanced.append(d1)
            if d2: balanced.append(d2)
        return balanced
```

---

## 4. Technical Specifications

### 4.1 Schema

```python
class LogDocument(BaseModel):
    id: str                  # UUID
    timestamp: datetime
    source: str              # "GitHub", "Zendesk", "Jira", "Slack"
    text_content: str
    relevance_score: float   # Cosine similarity score
    matched_query: str       # Which query produced this result
```

---

## 5. Testing Requirements & Red-Herring Filtering

| Test Category | Test Case | Expected Assertion |
|---------------|-----------|--------------------|
| Time Filtering | Log from July 15 matching "iOS checkout crash" | Excluded (timestamp outside pre-buffer window) |
| Red-Herring Filtering | Aug 5 log: "EMEA CDN 50ms latency elevation" | Ranked below iOS Stripe SDK logs for device query |
| Dimension Pre-Buffer | `region` driver query | Uses 72h pre-buffer window |
| Quota Balancing | Ambiguous mode (iOS 50% vs EMEA 48%) | Exactly 5 docs retrieved for iOS, 5 docs for EMEA |
| Ingestion Count | 90-day synthetic logs dataset | All 56+ documents embedded cleanly |
