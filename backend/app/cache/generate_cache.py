import json
import os
import asyncio
import pandas as pd
from pathlib import Path

# Imports of engine components
from app.engine.bsts import run_bsts_pipeline
from app.engine.decomposer import run_decomposition
from app.vectorstore.search import search_logs
from app.engine.hypothesis import generate_hypothesis
from app.engine.rag import build_rag_query

def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # If data is a pydantic model, it would need .model_dump()
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        json.dump(data, f, indent=2, default=str)

async def generate_golden_cache():
    print("Generating golden cache...")
    
    # Determine base directory (assume backend/)
    # This file is at backend/app/cache/generate_cache.py
    current_dir = Path(__file__).resolve().parent
    backend_dir = current_dir.parent.parent
    data_dir = backend_dir / "data"
    cache_dir = data_dir / "golden_cache"
    
    # 1. Load data
    metrics_path = data_dir / "synthetic_metrics.csv"
    logs_path = data_dir / "synthetic_logs.json"
    
    try:
        df = pd.read_csv(metrics_path)
        with open(logs_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except FileNotFoundError as e:
        print(f"Error loading data: {e}. Please ensure data generation (Phase 1) is complete.")
        # Proceed with dummies just for testing the imports
        df = pd.DataFrame()
        logs = []

    # 2. Run BSTS -> get timeseries + anomalies
    try:
        ts_result = run_bsts_pipeline(df)
    except Exception as e:
        print(f"Live BSTS failed or not implemented: {e}")
        ts_result = {"placeholder": "ts_result"}
        
    save_json(str(cache_dir / "timeseries.json"), ts_result)

    # 3. Run decomposition on the detected anomaly
    try:
        anomaly = ts_result.anomalies[0] if hasattr(ts_result, 'anomalies') and ts_result.anomalies else None
        decomp_result = run_decomposition(df, anomaly)
    except Exception as e:
        print(f"Live decomposition failed or not implemented: {e}")
        decomp_result = {"placeholder": "decomp_result"}
        
    save_json(str(cache_dir / "decomposition.json"), decomp_result)

    # 4. Run RAG + LLM hypothesis
    try:
        queries = build_rag_query(decomp_result)
        evidence = await search_logs(queries)
        
        # We assume evidence format aligns with what generate_hypothesis needs,
        # but since we are stubbing, we can mock it here
        from app.models.schemas import RAGResult
        rag_mock = RAGResult(decomposition=decomp_result, search_queries=[queries] if isinstance(queries, str) else queries, retrieved_logs=[])
        hypotheses = generate_hypothesis(rag_mock) # sync function in hypothesis.py
        root_cause_result = {
            "evidence": evidence,
            "hypotheses": hypotheses.model_dump() if hasattr(hypotheses, "model_dump") else hypotheses
        }
    except Exception as e:
        print(f"Live root cause analysis failed or not implemented: {e}")
        root_cause_result = {
            "evidence": [],
            "hypotheses": []
        }
        
    save_json(str(cache_dir / "root_cause.json"), root_cause_result)
    
    print(f"Cache generation complete! Output saved to {cache_dir}")

if __name__ == "__main__":
    asyncio.run(generate_golden_cache())
