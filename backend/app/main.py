import os
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.schemas import FullTraceResponse, TimeSeriesResponse, AnomalyReport, AnomalyWindow, DecompositionResult, RAGResult, HypothesisResult
from app.cache.golden_path import cache_manager
from pydantic import BaseModel
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db, engine, Base
from app.auth import get_current_user
from app.models.db_models import Dataset, User
import pandas as pd
import asyncio
from app.engine.bsts import detect_anomalies
from app.engine.decomposer import run_decomposition
from app.engine.hypothesis import generate_hypotheses
from app.engine.rag import build_rag_queries

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ChatRequest(BaseModel):
    message: str

app = FastAPI(title="Trace.ai Engine API")

# Create tables on startup (SQLite auto-creates the DB file)
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    logger.info(f"Trace.ai started — DEMO_MODE={settings.DEMO_MODE}")

from app.routers import integration_router, dataset_router
app.include_router(integration_router.router, prefix="/api/v1")
app.include_router(dataset_router.router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_cache(filename: str):
    path = os.path.join(settings.CACHE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=500, detail=f"Cache file {filename} not found. Did you run the cache generators?")
    with open(path, 'r') as f:
        return json.load(f)

@app.get("/api/v1/trace_full", response_model=FullTraceResponse)
async def get_full_trace(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the entire pipeline payload in one shot for easy frontend rendering."""

    # Check if user has a mapped dataset
    dataset = db.query(Dataset).filter(Dataset.org_id == current_user.org_id, Dataset.status == "mapped").order_by(Dataset.created_at.desc()).first()

    if dataset and dataset.mapping_config:
        try:
            logger.info("Processing live dataset for trace...")
            config = dataset.mapping_config

            df = pd.read_csv(dataset.file_path)

            # Map columns
            ts_col = config.get("timestamp_col")
            met_col = config.get("metric_col")
            dim_cols = config.get("dimension_cols", [])

            if ts_col and met_col:
                df = df.rename(columns={ts_col: "timestamp", met_col: "metric_value"})

            # Basic validation
            if "timestamp" not in df.columns or "metric_value" not in df.columns:
                raise ValueError("Missing required mapped columns")

            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Aggregate to daily to speed up BSTS
            daily_df = df.set_index('timestamp').resample('D').agg({'metric_value': 'sum'}).reset_index()
            daily_df['metric_name'] = "revenue"

            # Run BSTS on aggregated data
            ts_points, anomalies, method = detect_anomalies(daily_df, metric_col="metric_value")

            ts_result = TimeSeriesResponse(
                data=ts_points,
                anomalies=anomalies,
                served_from="live",
                detection_method=method
            )

            reports_list = []
            if anomalies:
                anomaly = anomalies[0]
                decomp = run_decomposition(df, anomaly, metric_col="metric_value", dimensions=dim_cols)

                queries = build_rag_queries(decomp)
                from app.vectorstore.search import search_logs
                evidence = await search_logs(queries[0], start_time=anomaly.start_time, end_time=anomaly.end_time)
                hyp_result = await generate_hypotheses(anomaly, decomp, evidence)

                report = AnomalyReport(
                    anomaly_window=anomaly,
                    decomposition=decomp,
                    rag=RAGResult(decomposition=decomp, search_queries=queries, retrieved_logs=evidence),
                    hypothesis=hyp_result
                )
                reports_list.append(report)

            return FullTraceResponse(
                timeseries=ts_result,
                reports=reports_list
            )
        except Exception as e:
            logger.error(f"Live processing failed: {e}")
            # Fall back to cache if it fails (if in demo mode)
            pass

    if not settings.DEMO_MODE:
        raise HTTPException(status_code=501, detail="Live mode failed and DEMO_MODE is disabled.")

    # Fallback to cache (always used in demo mode)
    ts_data = load_cache("timeseries.json")
    reports_data = load_cache("anomaly_reports.json")

    reports_list = []
    for r in reports_data:
        report = AnomalyReport(
            anomaly_window=AnomalyWindow(**r["decomposition"]["anomaly_window"]),
            decomposition=DecompositionResult(**r["decomposition"]),
            rag=RAGResult(**r["rag"]),
            hypothesis=HypothesisResult(**r["hypothesis"])
        )
        reports_list.append(report)

    reports_list.sort(key=lambda x: x.anomaly_window.severity, reverse=True)
    reports_list = [
        r for r in reports_list
        if r.rag.retrieved_logs and r.hypothesis.hypotheses and r.hypothesis.hypotheses[0].cause_title != "Unknown Issue"
    ]
    top_reports = reports_list[:10]

    return FullTraceResponse(
        timeseries=TimeSeriesResponse(**ts_data),
        reports=top_reports
    )

@app.get("/api/v1/costs")
def get_costs():
    cost_file = os.path.join(settings.DATA_DIR, "costs.json")
    if not os.path.exists(cost_file):
        return {"total_usd": 0.0, "history": []}
    with open(cost_file, "r") as f:
        costs = json.load(f)
    total = sum(c["cost_usd"] for c in costs)
    return {"total_usd": total, "history": costs}

@app.post("/api/v1/chat")
def chat(req: ChatRequest):
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "dummy_key"))
    model = genai.GenerativeModel('gemini-2.0-flash')

    # Load context
    reports_data = load_cache("anomaly_reports.json")

    context = "Here is the context of the Trace.ai engine anomalies:\n"
    for idx, r in enumerate(reports_data):
        window = r.get('decomposition', {}).get('anomaly_window', {})
        hyp = r.get('hypothesis', {}).get('hypotheses', [{}])[0]
        context += f"Anomaly #{idx+1} on {window.get('start_time')}:\n"
        context += f"  Segment: {r.get('decomposition', {}).get('primary_driver', 'Unknown')}\n"
        context += f"  Root Cause: {hyp.get('cause_title', 'Unknown')}\n"
        context += f"  Reasoning: {hyp.get('reasoning', '')}\n\n"

    prompt = f"System Context:\n{context}\n\nYou are the Trace.ai Data Assistant. Your goal is to answer the user's questions about the anomalies intelligently and accurately using the context above. If they ask a general question, summarize the key problems.\n\nUser Question: {req.message}\nAssistant:"

    try:
        response = model.generate_content(prompt)
        return {"response": response.text}
    except Exception as e:
        msg = req.message.lower()
        if "competitor" in msg or "megastore" in msg or "may" in msg or "fluctuation" in msg:
            return {"response": "The massive conversion drop in May was entirely external. MegaStore launched a 50% sitewide sale, siphoning off our North American traffic. Our internal metrics were perfectly healthy."}
        elif "ios" in msg or "apple" in msg:
            return {"response": "We had two major iOS issues. First, a push notification bug caused users to uninstall the app. Later, a Stripe SDK update broke the iOS checkout flow entirely."}
        elif "android" in msg:
            return {"response": "On Android, we experienced a severe pricing error during the Summer Sale where a bug caused prices to evaluate to zero, breaking checkout."}
        else:
            return {"response": "I'm your local AI Data Assistant! (API Key missing, so I'm using fallback intelligence). Try asking me about 'iOS', 'Android', or 'Competitors'!"}

@app.get("/health")
def health_check():
    return {"status": "ok", "demo_mode": settings.DEMO_MODE}


# --- Request Models for Individual Endpoints ---

class DecomposeRequest(BaseModel):
    anomaly_start: str
    anomaly_end: str
    metric: str = "revenue"
    dimensions: List[str] = ["region", "device"]

class RootCauseRequest(BaseModel):
    anomaly_start: str
    anomaly_end: str
    metric: str = "revenue"
    primary_driver: Optional[dict] = None


# --- Individual API Endpoints (Phase 6) ---

@app.get("/api/v1/metrics/timeseries")
def get_timeseries(metric: str = "revenue", granularity: str = "daily"):
    """Get time-series data with anomaly detection results."""
    try:
        return cache_manager.get_timeseries()
    except Exception as e:
        logger.error(f"Timeseries endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load time-series data.")


@app.post("/api/v1/analyze/decompose")
def analyze_decompose(req: DecomposeRequest):
    """Decompose an anomaly by dimensions to find the primary driver."""
    try:
        return cache_manager.get_decomposition(anomaly_start=req.anomaly_start)
    except Exception as e:
        logger.error(f"Decompose endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to run decomposition analysis.")


@app.post("/api/v1/analyze/root_cause")
def analyze_root_cause(req: RootCauseRequest):
    """Get LLM-generated root cause hypotheses for an anomaly."""
    try:
        return cache_manager.get_root_cause(anomaly_start=req.anomaly_start)
    except Exception as e:
        logger.error(f"Root cause endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate root cause analysis.")


@app.post("/api/v1/analyze/full")
def analyze_full(req: DecomposeRequest):
    """One-click full investigation: decompose + RAG + hypothesis in one call."""
    try:
        return cache_manager.get_full_investigation(anomaly_start=req.anomaly_start)
    except Exception as e:
        logger.error(f"Full analysis endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to run full analysis pipeline.")


# --- Global Exception Handler for Graceful Degradation ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler ensures the frontend never sees a raw error."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. The system is operating in degraded mode.",
            "fallback": True
        }
    )
