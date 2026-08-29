# Trace.ai 🚀

Trace.ai is an intelligent observability and root-cause analysis platform. It automates the process of finding anomalies in timeseries metrics (like sales, latency, conversion rates) and correlates them with system logs to instantly generate human-readable hypotheses for *why* the anomaly occurred.

Built with a modern stack, Trace.ai combines statistically rigorous anomaly detection (BSTS) with state-of-the-art Large Language Models (Google Gemini) and Vector Databases (ChromaDB).

## ✨ Features

- **Automated Anomaly Detection:** Uses Bayesian Structural Time Series (BSTS) via `statsmodels` to detect severe spikes or drops in timeseries data while filtering out normal seasonality and noise.
- **Metric Decomposition:** Automatically slices anomalies by dimensions (Region, Device, Channel, Product) to find the exact sub-segment driving the issue.
- **Semantic Log Correlation (RAG):** Uses **Google Gemini Cloud Embeddings** and **ChromaDB** to semantically search uploaded system logs for events that correlate with the exact time window and context of the anomaly.
- **AI Hypothesis Generation:** Feeds the anomaly data and correlated logs into Google Gemini to generate a definitive, human-readable root cause hypothesis.
- **Multi-Tenant Security:** Full integration with **Firebase Authentication**, ensuring users only see datasets and traces belonging to their own organization.
- **Modern Dashboard:** A sleek, dynamic React/Vite frontend featuring responsive charts, anomaly cards, and drag-and-drop file uploads.

## 🛠️ Recent Major Updates

- **Migrated to Gemini Embeddings:** Completely removed heavy PyTorch/`sentence-transformers` dependencies and replaced them with `google-genai` embeddings. This reduced backend memory usage by ~80%, entirely eliminating Out-Of-Memory (OOM) crashes on PaaS free tiers like Render.
- **Production CORS & Auth Security:** Hardened the FastAPI backend by implementing strict Firebase JWT token verification (disabling Demo Mode) and configuring Regex-based CORS middleware to seamlessly support dynamic Vercel preview domains.
- **Gunicorn Optimization:** Configured `Procfile` for production deployment with `uvicorn` workers optimized for memory-constrained environments.

## 🏗️ Architecture & Structure

Trace.ai is structured as a monolithic repository containing a decoupled frontend and backend.

```text
Trace-ai-demo/
│
├── backend/                  # Python FastAPI Backend
│   ├── app/
│   │   ├── engine/           # Core AI & Analytics Engine
│   │   │   ├── bsts.py         # Bayesian Structural Time Series detection
│   │   │   ├── decomposition.py# Dimensional metric slicing
│   │   │   ├── rag.py          # RAG query builder for ChromaDB
│   │   │   └── hypothesis.py   # Gemini prompt construction & generation
│   │   ├── vectorstore/      # ChromaDB Integration
│   │   │   ├── ingest.py       # Log parsing and Gemini Embedding generation
│   │   │   └── search.py       # Semantic similarity search
│   │   ├── routers/          # API Endpoints
│   │   │   ├── dataset_router.py
│   │   │   └── integration_router.py
│   │   ├── models/           # Pydantic Schemas & SQLAlchemy Models
│   │   ├── auth.py           # Firebase JWT Authentication
│   │   └── main.py           # FastAPI Application & CORS config
│   ├── requirements.txt      # Python dependencies
│   └── Procfile              # Render production startup command
│
├── frontend/                 # React + Vite Frontend
│   ├── src/
│   │   ├── components/       # Reusable UI components (Sidebar, Charts)
│   │   ├── pages/            # Application routes
│   │   │   ├── Dashboard.tsx   # Main visualization interface
│   │   │   ├── Upload.tsx      # Drag-and-drop ingestion
│   │   │   ├── Login.tsx       # Firebase Auth login
│   │   │   └── SignUp.tsx      # Firebase Auth registration
│   │   ├── firebase.ts       # Firebase client initialization
│   │   └── App.tsx           # React Router setup
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite configuration
│
└── sample_data/              # Example datasets for testing
```

## 🚀 Getting Started Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Firebase Project (for Authentication)
- A Google Gemini API Key

### Backend Setup
1. Navigate to the backend directory: `cd backend`
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `.\venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file in `backend/`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   DEMO_MODE=false
   FIREBASE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
   ```
6. Start the server: `python -m uvicorn app.main:app --reload --port 8000`

### Frontend Setup
1. Navigate to the frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Create a `.env` file in `frontend/`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_DEMO_MODE=false
   VITE_FIREBASE_API_KEY=...
   VITE_FIREBASE_AUTH_DOMAIN=...
   VITE_FIREBASE_PROJECT_ID=...
   ```
4. Start the dev server: `npm run dev`
5. Open your browser to `http://localhost:5173`

## ☁️ Deployment

- **Frontend:** Deployed via Vercel. Ensure all `VITE_` environment variables are added in Vercel settings.
- **Backend:** Deployed via Render using the `Procfile` (`web: gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker`). Ensure `FRONTEND_URL` and `GEMINI_API_KEY` are set in the Render environment settings.
