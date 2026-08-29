import os
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Dataset, User
from app.auth import get_current_user
from pydantic import BaseModel
from typing import Dict, List, Optional
import zipfile
import shutil
import logging

logger = logging.getLogger(__name__)

from app.config import settings
from app.vectorstore.ingest import ingest_logs

router = APIRouter(prefix="/datasets", tags=["datasets"])

UPLOAD_DIR = os.path.join("data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class MappingConfigRequest(BaseModel):
    timestamp_col: str
    metric_col: str
    dimension_cols: List[str]

@router.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # --- Phase 5: Re-enable live uploads, expect ZIP ---
    # The zip must contain metrics.csv and logs.json
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed (must contain metrics.csv and logs.json)")

    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{current_user.org_id}_{file_id}.zip")
    extract_dir = os.path.join(UPLOAD_DIR, f"{current_user.org_id}_{file_id}")
    
    with open(save_path, "wb") as f:
        f.write(await file.read())

    # Extract zip
    try:
        with zipfile.ZipFile(save_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except zipfile.BadZipFile:
        os.remove(save_path)
        raise HTTPException(status_code=400, detail="Invalid zip file")

    metrics_csv_path = None
    logs_json_path = None
    
    for root, dirs, files in os.walk(extract_dir):
        for name in files:
            if name == "metrics.csv":
                metrics_csv_path = os.path.join(root, name)
            elif name == "logs.json":
                logs_json_path = os.path.join(root, name)

    if not metrics_csv_path:
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.remove(save_path)
        raise HTTPException(status_code=400, detail="metrics.csv not found in zip")
        
    if not logs_json_path:
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.remove(save_path)
        raise HTTPException(status_code=400, detail="logs.json not found in zip")

    try:
        # Read just the first few rows to get columns
        df = pd.read_csv(metrics_csv_path, nrows=5)
        columns = df.columns.tolist()
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.remove(save_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    # Ingest logs into Chroma in the background so we don't block the request
    try:
        background_tasks.add_task(ingest_logs, file_id, logs_json_path)
    except Exception as e:
        logger.error(f"Failed to queue log ingestion: {e}")

    dataset = Dataset(
        id=file_id,
        org_id=current_user.org_id,
        file_name=file.filename,
        file_path=metrics_csv_path, # store the CSV path for engine
        status="uploaded"
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "columns": columns,
        "message": "File uploaded successfully. Please map the columns."
    }

@router.post("/{dataset_id}/map")
def map_dataset_columns(
    dataset_id: str,
    config: MappingConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # --- Phase 1: Column mapping disabled in DEMO_MODE ---
    # Removed block to allow saving mapping config.

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.org_id == current_user.org_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    dataset.mapping_config = config.dict()
    dataset.status = "mapped"
    db.commit()
    
    return {"message": "Mapping configuration saved successfully"}

@router.get("/")
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    datasets = db.query(Dataset).filter(Dataset.org_id == current_user.org_id).all()
    return datasets
