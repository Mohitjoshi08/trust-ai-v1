# Trace.ai Project Handoff

## 1. Project Overview & Vision (Context for Outsiders)

**What is Trace.ai?**
Trace.ai is a full-stack web application designed to be an **evidence-backed KPI investigation engine**. When a company's business metric (KPI) suddenly drops or spikes (an anomaly), analysts typically spend hours digging through logs, databases, and dashboards to figure out *why*. Trace.ai automates this investigation. 

**The Goal:**
The product takes a time-series dataset, detects anomalies using statistical models (BSTS), decomposes the anomaly to find the primary driver (e.g., "iOS traffic dropped"), searches semantic operational logs using RAG (Retrieval-Augmented Generation), and then uses an LLM (Google Gemini) to generate hypotheses for the root cause. 

**The Architecture:**
- **Backend:** Python FastAPI, SQLAlchemy (SQLite), Pandas (for statistical decomposition), ChromaDB (for RAG log retrieval), and Google GenAI.
- **Frontend:** React + Vite, built with modern CSS variables, responsive layouts, and interactive charts.
- **Database:** Local SQLite (`trace_ai.db`).

## 2. Current State of the Project (What We Have Done)

We took an initially broken, unrunnable MVP and transformed it into a robust, locally runnable application.

**Key Accomplishments:**
- **Dependency & Environment Fixes:** Resolved strict version conflicts in Python. Removed the broken `psycopg2-binary` dependency and added missing core libraries (`chromadb`, `openai`).
- **Database Migration:** Migrated the backend from PostgreSQL to a zero-setup local `SQLite` database.
- **Demo Mode & Auth Bypass:** Implemented a robust `DEMO_MODE`. The frontend completely mocks the Firebase `auth` object, allowing the user to sign up, log in, and use the app without valid Firebase API keys. The backend was also modified to bypass actual database user checks.
- **Live Data Support:** Modified the backend so that even in Demo Mode, if the user uploads a live dataset, it will process their live data instead of strictly defaulting to the hardcoded golden cache (`.json` files).
- **Engine Bug Fixes:** Fixed a critical `TypeError` in the statistical `decomposer.py`.
- **UI Enhancements:** Added a reusable `Sidebar.tsx`, Logout functionality, and "Show Password" / "Confirm Password" validations to the Sign-Up page.

## 3. The Implementation Plan (What Is Left To Do)

The original MVP is working, but the overarching goal of this project (as defined in `plan/TRACE_IMPLEMENTATION_PLAN.md`) is to upgrade Trace.ai. Currently, the MVP just asks an LLM for a single root cause and slaps a fake "92% Confidence" score on it. We need to move away from this and present **multiple hypotheses backed by a deterministic Evidence Matrix**.

**Pending Features (P0 - Must Have):**
1. **Multi-Hypothesis Engine:** Refactor the backend to generate 2–3 competing hypotheses instead of just one. If the evidence is ambiguous, the app should explicitly state that it cannot decide.
2. **Evidence Matrix:** Create a deterministic matrix (Pass/Fail/Unknown) for each hypothesis based on concrete evidence (e.g., "Did the deployment happen before the anomaly? -> PASS").
3. **Evidence Strength Presentation:** Replace the user-facing percentage confidence score with strict qualitative labels: `HIGH`, `MEDIUM`, `LOW`, or `INSUFFICIENT` evidence.
4. **Evidence Lineage:** Every conclusion must be traceable back to exact source logs (e.g., temporal alignment, deployment event, symptom logs).
5. **Adaptive Retrieval Windows:** RAG logic must start with a small time window and expand sequentially (e.g., ±72 hours, ±7 days) only if evidence is insufficient.
6. **Recovery Validation:** Detect if a recovery action (like a code rollback) actually caused the metric to recover in the time-series data.
7. **Reconciled Contribution Logic:** KPI decomposition must reconcile in absolute units (e.g., -$15,000) and flag warnings if the segment drops do not perfectly equal the aggregate drop.

**Pending Features (P1/P2):**
- A visual Investigation Timeline UI.
- Counterfactual / expected-signature checks.
- Red-herring rejection display (explaining to the user *why* certain logs were ignored by the AI).
- Analyst feedback loops (Correct / Incorrect).

## 4. Current Problems & Technical Challenges

If you are picking up this project, here are the immediate technical hurdles you will face:

- **Massive Schema Refactoring:** Moving to the Evidence Matrix and Multi-Hypothesis structure requires completely rewriting the Pydantic schemas in `app.models.schemas` (`AnomalyReport`, `RAGResult`, `HypothesisResult`, etc.). The frontend React components (`Dashboard.tsx`) will subsequently break and need a major overhaul to render the new data structures.
- **Live Data vs. Golden Logs Mismatch:** The RAG system (`search_logs`) currently queries against synthetic, hardcoded operational logs. If a user uploads a totally random live dataset, the LLM hypotheses might hallucinate or crash because the anomaly won't match any of the embedded logs.
- **Google GenAI SDK Deprecation:** The backend prints a warning on startup: `All support for the google.generativeai package has ended. Please switch to the google.genai package.` The `chat` endpoint and `hypothesis.py` generation logic need to be migrated to the new Google GenAI SDK. 
- **Prompt Engineering:** The current prompts in `hypothesis.py` are basic. You will need to design highly constrained prompts that force the LLM to output structured competing hypotheses without inventing fake evidence IDs.
