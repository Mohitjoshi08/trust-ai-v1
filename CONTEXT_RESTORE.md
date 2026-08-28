# Trace.ai - Session Context & State Restoration

## 1. Project Objective
We are transforming the **Trace.ai** React/FastAPI application from a prototype that uses hardcoded data into a multi-tenant SaaS platform. The key goal is to build an **Automated Integration Framework** (replacing manual CSV uploads) that syncs data hourly from platforms like Shopify/Snowflake and uses an **LLM (Gemini) to automatically map column schemas**.

## 2. What Has Been Completed So Far
- **Database & Models:** Configured SQLAlchemy. Created `Organization`, `User`, and `Dataset` models in `backend/app/models/db_models.py`. 
- **Database Engine:** Currently using **SQLite** (`sqlite:///./trace_ai.db`) for smooth local testing. Migrations have been run successfully.
- **Authentication:** Configured Firebase Email/Password Auth. Created `auth.py` in the backend to automatically verify Firebase JWTs and provision Users/Orgs in the database.
- **Frontend Refactoring:** Added `react-router-dom`. Created `Login.tsx`, `SignUp.tsx` (with email verification), `Upload.tsx`, and refactored the main app into `Dashboard.tsx` with Auth Guards (`RequireAuth`).
- **PRD:** A complete Product Requirements Document (`TRACE_AI_PRD.md`) was generated and approved.

## 3. Current In-Progress Task (Where We Left Off)
Right before the crash, we were actively building the **Connector Framework**. Two parallel subagents were tasked with the following:

### Backend Requirements (To be completed):
- Add `Integration` model to `db_models.py`.
- Create `app/connectors/base.py` (Abstract `BaseConnector`).
- Create concrete connectors: `csv_connector.py`, `shopify_connector.py`, `google_analytics_connector.py`, and `stripe_connector.py`.
- Create `app/connectors/registry.py`.
- Create `app/services/mapping_service.py` using `google.generativeai` to auto-map schemas.
- Create `app/routers/integration_router.py` with CRUD, connection testing, and LLM mapping endpoints.
- Update `app/main.py` to include the `integration_router`.

### Frontend Requirements (To be completed):
- Create `src/pages/Integrations.tsx` (Hub to view available and connected integrations).
- Create `src/pages/ConnectIntegration.tsx` (3-step wizard: Credentials -> AI Auto-Map -> Success).
- Update `src/App.tsx` routing to include these new pages.

## 4. Instructions for the New Agent
1. **Do not repeat the initial setup.** The dependencies are installed, and Firebase/SQLite are already configured.
2. **Resume the Integration Build:** Read the backend and frontend requirements above and immediately begin writing the code for the Connector Framework and the React Integration pages.
3. **Restart Servers:** You may want to launch the backend (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`) and frontend (`npm run dev`) in the background to verify the new code as you write it.
