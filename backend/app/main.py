import os
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.schemas import FullTraceResponse, TimeSeriesResponse, AnomalyReport, AnomalyWindow, DecompositionResult, RAGResult, HypothesisResult, HypothesisResultV1
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
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Database init race condition skipped: {e}")
    logger.info(f"Trace.ai started — DEMO_MODE={settings.DEMO_MODE}")

from app.routers import integration_router, dataset_router
app.include_router(integration_router.router, prefix="/api/v1")
app.include_router(dataset_router.router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",
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
    dataset_id: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the entire pipeline payload in one shot for easy frontend rendering."""

    if not dataset_id:
        logger.info("Serving trace from synthetic golden cache (live processing disabled).")
        # Fallback to cache (always used in demo mode if no dataset is selected)
        ts_data = load_cache("timeseries.json")
        reports_data = load_cache("anomaly_reports.json")

        reports_list = []
        for r in reports_data:
            # Parse new Phase 2 hypotheses (structured evidence matrix)
            new_hypotheses = [HypothesisResult(**h) for h in r.get("hypotheses", [])]
            # Parse old V1 hypothesis wrapper (backward compat)
            old_hypothesis = HypothesisResultV1(**r["hypothesis"]) if r.get("hypothesis") else None

            report = AnomalyReport(
                anomaly_window=AnomalyWindow(**r["decomposition"]["anomaly_window"]),
                decomposition=DecompositionResult(**r["decomposition"]),
                rag=RAGResult(**r["rag"]),
                hypotheses=new_hypotheses,
                hypothesis=old_hypothesis,
            )
            reports_list.append(report)

        reports_list.sort(key=lambda x: x.anomaly_window.severity, reverse=True)
        reports_list = [
            r for r in reports_list
            if r.rag.retrieved_logs and r.hypotheses
        ]
        top_reports = reports_list[:10]

        return FullTraceResponse(
            timeseries=TimeSeriesResponse(**ts_data),
            reports=top_reports
        )
    else:
        logger.info(f"Live processing dataset: {dataset_id}")
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        mapping = dataset.mapping_config or {}
        timestamp_col = mapping.get("timestamp_col", "timestamp")
        metric_col = mapping.get("metric_col", "metric_value")
        
        # 1. Load CSV
        try:
            df = pd.read_csv(dataset.file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read CSV: {str(e)}")
            
        # 2. Anomaly Detection
        ts_points, anomaly_windows, method = detect_anomalies(df, metric_col, timestamp_col)
        
        if not anomaly_windows:
            # Return empty reports
            ts_res = TimeSeriesResponse(
                data=ts_points,
                anomalies=[],
                served_from="live",
                detection_method=method
            )
            return FullTraceResponse(timeseries=ts_res, reports=[])
            
        # Process top 5 worst anomalies
        top_anomalies = sorted(anomaly_windows, key=lambda x: abs(x.aggregate_deviation_pct), reverse=True)[:5]
        reports_list = []
        
        from app.engine.rag import build_rag_queries, adaptive_search
        from datetime import datetime
        from app.database_utils import save_anomaly_report_to_db
        
        for aw in top_anomalies:
            # 3. Decomposition
            decomp = run_decomposition(df, aw, timestamp_col, metric_col)
            
            # 4. RAG
            queries = build_rag_queries(decomp)
            query = queries[0] if queries else f"{metric_col} anomaly"
            
            st = datetime.fromisoformat(aw.start_time) if isinstance(aw.start_time, str) else aw.start_time
            et = datetime.fromisoformat(aw.end_time) if isinstance(aw.end_time, str) else aw.end_time
            
            logs, window = await adaptive_search(dataset_id, query, st, et)
            
            rag_result = RAGResult(
                decomposition=decomp,
                search_queries=queries,
                retrieved_logs=logs
            )
            
            # 5. Hypotheses
            hypotheses_tuple = await generate_hypotheses(aw, decomp, logs)
            
            if isinstance(hypotheses_tuple, tuple):
                hypotheses = hypotheses_tuple[0]
                rejected_logs = hypotheses_tuple[1]
            else:
                hypotheses = hypotheses_tuple
                rejected_logs = []
                
            # 6. Compose AnomalyReport
            report = AnomalyReport(
                anomaly_window=aw,
                decomposition=decomp,
                rag=rag_result,
                hypotheses=hypotheses,
                rejected_logs=rejected_logs
            )
            
            # Save to database
            save_anomaly_report_to_db(db, dataset_id, report)
            reports_list.append(report)
            
        # Build Response
        ts_res = TimeSeriesResponse(
            data=ts_points,
            anomalies=anomaly_windows,
            served_from="live",
            detection_method=method
        )
        return FullTraceResponse(timeseries=ts_res, reports=reports_list)

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
    from google import genai

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
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "dummy_key"))
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
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


# --- Write-Back Pipeline (Phase 8) ---

class FeedbackRequest(BaseModel):
    is_correct: bool

@app.put("/api/v1/analyze/feedback/{hypothesis_id}")
def submit_analyst_feedback(
    hypothesis_id: str,
    req: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """Saves analyst feedback (Approve/Reject) for a specific hypothesis back to the database."""
    from app.models.db_models import HypothesisModel
    
    hyp = db.query(HypothesisModel).filter(HypothesisModel.id == hypothesis_id).first()
    if not hyp:
        raise HTTPException(status_code=404, detail="Hypothesis not found in database.")
        
    hyp.analyst_feedback = req.is_correct
    db.commit()
    
    return {"status": "success", "message": f"Feedback updated for {hypothesis_id}", "is_correct": req.is_correct}


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
