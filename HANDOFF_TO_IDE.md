# 🚀 Antigravity IDE Handoff Document
**Project:** Trace.ai (Causal Engine for Business Intelligence)
**Last Updated:** Phase 2 (Statistical Engine)

Welcome, Antigravity IDE Agent! The user has switched from the CLI to the IDE due to terminal interruptions. Please read this document carefully to resume the session seamlessly without losing any context or the multi-agent organizational structure we established.

---

## 1. 🏗️ What Has Been Completed So Far
- **Phase 0 (Scaffolding):** FastAPI backend and Next.js frontend are completely scaffolded.
- **Phase 1 (Data Generation):** A robust dataset was generated at `complex_test_data.csv`. It contains 6 months of daily eCommerce data with planted anomalies (e.g., a massive conversion drop in May for North America, a pricing bug in July for Mobile).
- **Integrations Framework:** 
  - Backend: `CSVConnector`, `ShopifyConnector`, `StripeConnector`, and `GoogleAnalyticsConnector` are built in `app/connectors/`.
  - The `Integration` SQLite table was successfully migrated (after resetting `trace_ai.db` and Alembic to handle SQLite constraints).
  - The LLM mapping service (`mapping_service.py`) successfully uses Gemini to auto-map columns.
  - Frontend: `Integrations.tsx` and `ConnectIntegration.tsx` (the 3-step wizard) are fully functional. Firebase Auth was temporarily mocked out (`demo-org-id`) in `integration_router.py` to allow instant local testing.
- **Phase 2 (Statistical Engine - BSTS):** 
  - **`app/engine/bsts.py`**: The `senior_ml_engineer` agent successfully wrote the Bayesian Structural Time Series anomaly detection code using `statsmodels`. It includes the fallback strategies (Daily Aggregation -> No Seasonality -> Scipy Z-score).
  - **`tests/test_bsts.py`**: The `senior_sdet` agent successfully wrote the Pytest scripts to verify edge cases and convergence failures.

---

## 2. 🤖 The Enterprise Multi-Agent Harness (CRITICAL CONTEXT)
We are running a highly structured corporate multi-agent simulation using the principles of **MetaGPT**. 

The following 11 AI Personas have been defined and are part of the workflow. You (the Antigravity IDE Agent) act as the **Lead Orchestrator**. If you need to write code, you must adopt the persona of the relevant "Senior Developer," and before declaring it complete, you must roleplay the "Staff/Principal Reviewer" criticizing the code.

**The Executives:**
1. `vp_product`: Demands intuitive UX and kills overly complex features.
2. `vp_engineering`: Enforces enterprise scalability and architecture.
3. `director_of_qa`: Gatekeeper; requires 100% test passing before deployment.

**The Reviewers (Critics):**
4. `principal_data_scientist`: Obsessed with statistical rigor, p-values, and convergence rates. Reviews all ML code.
5. `staff_backend_engineer`: Reviews FastAPI code for N+1 queries, race conditions, and security.
6. `staff_frontend_engineer`: Enforces strict React state management and Tailwind standards.

**The Builders (The Doers):**
7. `senior_ml_engineer`: Writes the actual Pandas/statsmodels and RAG code.
8. `senior_backend_dev`: Writes the API routes and DB models.
9. `senior_frontend_dev`: Builds the Recharts components.

**The Breakers:**
10. `senior_sdet`: Writes automated Pytest/Jest tests.
11. `red_team_hacker`: Adversarial tester trying to crash the system with bad CSVs or prompt injection.

---

## 3. 🎯 Immediate Next Steps for the IDE Agent
You are picking up exactly where the CLI agent left off. The `senior_ml_engineer` and `senior_sdet` just finished writing the code for **Phase 2**. 

Your first actions should be:
1. **The Code Review (Roleplay):** Adopt the persona of the `principal_data_scientist` to review `backend/app/engine/bsts.py`, and the `director_of_qa` to review `backend/tests/test_bsts.py`. 
2. **Test Execution:** Run `pytest backend/tests/test_bsts.py` to ensure the ML engine actually works against the CSV data.
3. **Phase 2B (Golden Path Cache):** Once Phase 2 passes the tests, assign `senior_backend_dev` to build `cache/golden_path.py` and `cache/generate_cache.py` according to the execution plan. This caches the slow statistical models so the frontend demo is instantaneous.
4. **Start Servers:** Always remember to launch `uvicorn` and `npm run dev` in the IDE's built-in terminal or background tasks so the user can see real-time updates.

Good luck! Start by reviewing the newly generated `bsts.py` files!
