# Trace.ai

Trace.ai is an intelligent observability and root-cause analysis platform. It automates the process of finding anomalies in timeseries metrics and correlates them with system logs to instantly generate human-readable hypotheses for why an anomaly occurred.

## Implementation Approach

The implementation leverages a decoupled frontend and backend architecture to ensure scalability and maintainability.
1. **Frontend**: Developed using React and Vite, focusing on a responsive and dynamic user interface. The UI components are modular, facilitating ease of updates and state management.
2. **Backend**: Built with FastAPI, the backend handles API routing, authentication, and core analytic engine processes. 
3. **Analytics Engine**: Employs Bayesian Structural Time Series (BSTS) models via `statsmodels` for anomaly detection, filtering out expected seasonality and noise.
4. **Log Correlation & Root Cause**: Utilizes Google Gemini embeddings and ChromaDB for semantic search across system logs, feeding context into LLM prompts to synthesize actionable insights.

## Solution Architecture

The repository is structured as a monolithic repository containing independent frontend and backend modules.

- **backend/**: Python FastAPI application containing the core AI engine and API endpoints.
  - **app/engine/**: Core analytic scripts including BSTS anomaly detection and Hypothesis generation.
  - **app/vectorstore/**: ChromaDB integration for semantic log storage and retrieval.
  - **app/routers/**: REST API routing layers.
  - **app/models/**: Pydantic schemas and database models.
- **frontend/**: React + Vite application for the client-side dashboard and visualization.
  - **src/components/**: Reusable UI widgets and charts.
  - **src/pages/**: Core application views (Dashboard, Upload).

## Dependencies

### Backend
- Python 3.10+
- FastAPI (Web framework)
- Uvicorn (ASGI server)
- Statsmodels (Time series analysis)
- ChromaDB (Vector database)
- Google GenAI (Embeddings and LLM)
- Pydantic (Data validation)

### Frontend
- Node.js 18+
- React 18
- Vite
- TailwindCSS (Styling)
- Recharts (Data visualization)

## Execution Instructions

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables. Create a `.env` file in the `backend/` directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   DEMO_MODE=true
   ```
5. Start the server:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the dependencies:
   ```bash
   npm install
   ```
3. Configure environment variables. Create a `.env` file in the `frontend/` directory:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_DEMO_MODE=true
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
5. Access the application in your browser at `http://localhost:5173`.
