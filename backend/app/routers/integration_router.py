from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.models.db_models import Integration, User
from app.connectors.registry import ConnectorRegistry
from app.services.mapping_service import generate_schema_mapping

# Mock get_current_user for local testing to bypass Firebase Auth setup
def get_current_user():
    return type('User', (), {'org_id': 'demo-org-id'})()

router = APIRouter(prefix="/integrations", tags=["Integrations"])

class IntegrationCreate(BaseModel):
    platform: str
    display_name: str
    credentials: Dict[str, Any]

class IntegrationResponse(BaseModel):
    id: str
    platform: str
    display_name: str
    status: str
    
    class Config:
        from_attributes = True

@router.get("/available")
def get_available_integrations():
    """Returns a list of all available integrations and their required fields."""
    return ConnectorRegistry.get_all_connectors()

@router.post("/", response_model=IntegrationResponse)
def create_integration(
    integration: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        ConnectorClass = ConnectorRegistry.get_connector(integration.platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    connector = ConnectorClass()
    if not connector.test_connection(integration.credentials):
        raise HTTPException(status_code=400, detail="Invalid credentials or unable to connect.")
        
    new_integration = Integration(
        org_id=current_user.org_id,
        platform=integration.platform,
        display_name=integration.display_name,
        credentials=integration.credentials,
        status="connected"
    )
    
    db.add(new_integration)
    db.commit()
    db.refresh(new_integration)
    return new_integration

@router.get("/", response_model=List[IntegrationResponse])
def get_integrations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return db.query(Integration).filter(Integration.org_id == current_user.org_id).all()

@router.post("/{integration_id}/auto-map")
def auto_map_integration(
    integration_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.org_id == current_user.org_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    try:
        ConnectorClass = ConnectorRegistry.get_connector(integration.platform)
        connector = ConnectorClass()
        schema = connector.fetch_schema(integration.credentials)
        
        mapping = generate_schema_mapping(integration.platform, schema)
        
        integration.mapping_config = mapping
        db.commit()
        return {"mapping": mapping}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping failed: {str(e)}")
