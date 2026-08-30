You are an expert AI software engineer and architect. I am building a product called **Trace.ai**, an AI-powered root-cause analysis and anomaly detection platform. I need you to help me understand, expand, and improve this system. 

Here is everything you need to know about the product:

### 1. Product Overview
**Trace.ai** ingests time-series metrics and system logs, identifies statistical anomalies in the metrics, and uses an AI-powered Retrieval-Augmented Generation (RAG) pipeline to cross-reference those anomalies with system logs. It ultimately generates structured "Hypotheses" (potential root causes) and an "Evidence Matrix" (logs that support or refute the hypothesis) to help engineers debug incidents faster.

### 2. Tech Stack
* **Frontend:** React (TypeScript), Vite, TailwindCSS (or modern Vanilla CSS). It features a dashboard that displays the anomaly report, ranked hypotheses, and an evidence matrix.
* **Backend:** Python, FastAPI, SQLAlchemy (SQLite database for relational data like reports, datasets, and hypotheses).
* **Vector Database:** ChromaDB (used for storing and searching system logs).
* **AI Models:** Google Gemini (Gemini-3.5-flash for hypothesis generation and reasoning, and gemini-embedding-2 for embedding text into ChromaDB).

### 1. Core Architecture & API Flow
Trace.ai is designed to take raw CSV files of telemetry and find the absolute root cause of an anomaly. 
The main orchestrator (`backend/app/main.py`) exposes `/api/v1/trace_full` which takes a `dataset_id`. The exact flow is:
1. **Data Loading:** The CSV is loaded via Pandas. It automatically detects timestamp and metric columns.
2. **Anomaly Detection:** The time-series data is passed to the BSTS (Bayesian Structural Time Series) engine.
3. **Decomposition:** The metrics are decomposed, pulling out the exact `AnomalyWindow` (start time, end time, severity).
4. **Adaptive RAG:** Using the time boundaries of the anomaly, the system queries the ChromaDB vectorstore.
5. **Hypothesis Engine:** The LLM generates the root cause analysis using structured outputs.
6. **Persistence:** The results are mapped to SQLAlchemy models and stored in SQLite.

### 2. Time-Series Logic (`app/engine/bsts.py`)
The system relies heavily on `tfp.sts` (TensorFlow Probability Structural Time Series) for statistical rigor:
* **Preprocessing:** It drops NaNs, sorts chronologically, and ensures the series is long enough. 
* **Modeling:** It builds a structural model with a `LocalLinearTrend` and multiple `Seasonal` components depending on the timeframe (e.g., daily seasonality with 24 hours, weekly with 7 days).
* **Variational Inference:** It fits the model using Surrogate Posteriors and draws parameter samples to forecast the "expected" non-anomalous state.
* **Anomaly Flagging:** It calculates the 95% credible intervals (upper and lower bounds). Any actual metric point falling outside these bounds is flagged as anomalous.
* **Clustering:** Contiguous anomalous points are clustered into an `AnomalyWindow`. The `severity_score` is calculated as the cumulative sum of the absolute difference between the actual value and the upper bound for that cluster.

### 3. Vector Database & RAG Logic (`app/engine/rag.py` & `vectorstore/`)
Trace.ai uses **ChromaDB** for log storage and Google's `gemini-embedding-2` for generating vectors.
* **Ingestion (`ingest.py`):** Logs are batched in groups of 20. Because the new Google GenAI SDK aggregates string lists into a single multi-part prompt embedding, the ingestion logic explicitly loops over the 20 texts to embed them sequentially, guaranteeing a 1:1 mapping of logs to vectors to prevent ChromaDB crashes.
* **Adaptive Search (`rag.py`):** The system implements a tiered search strategy. 
  - **Tier 1:** It queries the vector store for logs within ±24 hours of the anomaly's center.
  - **Fallback Tier 2:** If no logs meet the cosine similarity threshold (configurable, currently `-10.0` to bypass strict filtering for demos), it expands the search window to ±72 hours.
* **Post-Processing:** Retrieved logs are deduplicated by ID and sorted by relevance.

### 4. The Hypothesis Engine (`app/engine/hypothesis.py`)
This is the "Brain" of the system, calling `gemini-3.5-flash` with a strict Pydantic JSON schema output (`HypothesesResponse`).
* **Deterministic Evaluation:** Before hitting the LLM, the system runs `evaluate_evidence()`. This is a rule-based engine that scans the raw RAG logs for specific substrings (e.g., `deploy`, `PR`, `error`, `exception`, `latency`, `timeout`, `config`). It automatically checks off deterministic evidence like "Missing deployment logs" or "Error spikes." This provides grounded factual checks *before* the LLM can hallucinate.
* **LLM Reasoning:** The LLM receives a massive prompt containing the BSTS decomposition (trend, anomaly severity), the exact time bounds, the raw texts of the RAG logs, and the pre-computed deterministic evidence matrix.
* **Output Generation:** The LLM generates 1 to 5 competing `Hypothesis` objects (e.g., "Database outage," "Bad deployment"). It ranks them by probability and links them to the factual evidence.
* **Rate Limiting:** A custom local JSON-based rate limiter enforces Google's free-tier restrictions (4 Requests Per Minute, 18 Requests Per Day), putting the thread to `asyncio.sleep` if limits are hit.

### 5. Database & Persistence (`app/database_utils.py` & `db_models.py`)
* **SQLAlchemy:** The system uses SQLite. The models include `Dataset`, `AnomalyReportModel`, `HypothesisModel`, and `EvidenceModel`.
* **The Unique Constraint Fix:** Because the LLM evaluates the evidence matrix *once*, it often returns the exact same Evidence ID for multiple hypotheses (e.g., a missing deployment log is evidence for both a "Config change" hypothesis and an "Organic traffic" hypothesis). To prevent a SQLite `UNIQUE constraint failed` crash on the primary key, `database_utils.py` forcibly injects the hypothesis ID into the evidence ID (`f"{hyp.id}-{ev.id}"`) before saving it to the database.

### 6. Dataset Schemas (The Input Data)
The system ingests a ZIP file (e.g., `sample_10mb_dataset.zip`) containing two files:
* `metrics.csv`: The time-series telemetry. 
  - **Columns:** `timestamp` (ISO8601), `region`, `device`, `channel`, `product`, `value` (float).
* `logs.json`: The system logs.
  - **Schema:** Array of JSON objects containing `id` (UUID string), `timestamp` (ISO8601), `source` (e.g., `deploy-bot`, `datadog-monitor`), `text_content` (the log message string).

### 7. UI / UX Design Language (Frontend)
The frontend uses React (TypeScript) and Vite with a strict, bespoke enterprise CSS architecture (`index.css`):
* **Typography:** Uses the modern `Geist` font stack. Employs tight typography tracking (`letter-spacing: -0.01em`) and dense body copy (`13px`) for an information-dense, developer-centric feel.
* **Layout:** Built around a structural grid with a main dashboard area, a rigid `260px` Sidebar, and a `320px` Evidence Feed drawer.
* **Aesthetics:** Sharp edges (`border-radius: 0px` to `2px`), deep Slate color palette (`#0f172a`), and flat enterprise styling that mimics high-end developer tools like Linear or Datadog.
* **Components:** 
  - `Upload.tsx`: Handles drag-and-drop ZIP dataset ingestion, POSTing to `/api/v1/trace_full`.
  - `Dashboard.tsx`: Renders the Report ID by mapping the LLM's hypotheses into visual cards, placing the deterministic evidence matrix in a right-hand feed, and overlaying anomalies on metric charts.

### 8. Your Open-Ended Mission
I am giving you full creative and architectural freedom. Based on the deep context above:
1. **Critique the Architecture:** Where are the bottlenecks? How would you improve the BSTS parameters, the RAG search tiers, or the deterministic evaluation engine?
2. **Suggest Features:** What killer features is this dashboard missing that would make it a world-class root cause analysis tool?
3. **Write Code:** Feel free to suggest refactors (e.g., implementing LangChain for RAG, improving the LLM prompt) or propose sleek, modern UI components for the React dashboard.

Please start by giving me your high-level thoughts on this architecture, and then tell me what you think we should build or improve first.
