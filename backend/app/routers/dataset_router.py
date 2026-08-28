import os
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Dataset, User
from app.auth import get_current_user
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/datasets", tags=["datasets"])

UPLOAD_DIR = os.path.join("data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class MappingConfigRequest(BaseModel):
    timestamp_col: str
    metric_col: str
    dimension_cols: List[str]

@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{current_user.org_id}_{file_id}.csv")
    
    with open(save_path, "wb") as f:
        f.write(await file.read())

    try:
        # Read just the first few rows to get columns
        df = pd.read_csv(save_path, nrows=5)
        columns = df.columns.tolist()
    except Exception as e:
        os.remove(save_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    dataset = Dataset(
        id=file_id,
        org_id=current_user.org_id,
        file_name=file.filename,
        file_path=save_path,
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
