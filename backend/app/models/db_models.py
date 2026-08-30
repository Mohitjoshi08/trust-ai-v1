import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Integer, Float
from sqlalchemy.orm import relationship
from app.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    datasets = relationship("Dataset", back_populates="organization")
    integrations = relationship("Integration", back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    firebase_uid = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    role = Column(String, default="admin")  # admin, viewer
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    platform = Column(String)  # 'shopify', 'google_analytics', 'snowflake', 'stripe', 'csv'
    display_name = Column(String)  # User-friendly name like "My Shopify Store"
    credentials = Column(JSON, nullable=True)  # Encrypted API keys / OAuth tokens
    sync_frequency = Column(String, default="hourly")  # hourly, daily, manual
    mapping_config = Column(JSON, nullable=True)  # LLM-suggested mapping
    status = Column(String, default="pending")  # pending, connected, syncing, error
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="integrations")

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    integration_id = Column(String, ForeignKey("integrations.id"), nullable=True)
    file_name = Column(String)
    file_path = Column(String)
    mapping_config = Column(JSON, nullable=True) # { "timestamp": "Date", "metric": "Sales", "dimensions": ["Region"] }
    status = Column(String, default="uploaded") # uploaded, mapped, processing, ready
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="datasets")
    integration = relationship("Integration")
    reports = relationship("AnomalyReportModel", back_populates="dataset")

class AnomalyReportModel(Base):
    __tablename__ = "anomaly_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    dataset_id = Column(String, ForeignKey("datasets.id"))
    anomaly_start = Column(DateTime)
    anomaly_end = Column(DateTime)
    metric_name = Column(String)
    severity = Column(Float)
    recovered = Column(Boolean, nullable=True)
    
    # Store the complex dicts here rather than splitting them into their own tables for now
    raw_decomposition = Column(JSON)
    raw_rag = Column(JSON)
    rejected_logs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="reports")
    hypotheses = relationship("HypothesisModel", back_populates="report", cascade="all, delete-orphan")

class HypothesisModel(Base):
    __tablename__ = "hypotheses"

    id = Column(String, primary_key=True, index=True)
    report_id = Column(String, ForeignKey("anomaly_reports.id"))
    rank = Column(Integer)
    title = Column(String)
    description = Column(String)
    evidence_strength = Column(String)
    analyst_feedback = Column(Boolean, nullable=True)
    recommended_actions = Column(JSON, nullable=True)

    report = relationship("AnomalyReportModel", back_populates="hypotheses")
    evidence_matrix = relationship("EvidenceModel", back_populates="hypothesis", cascade="all, delete-orphan")

class EvidenceModel(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True, index=True)
    hypothesis_id = Column(String, ForeignKey("hypotheses.id"))
    log_id = Column(String, nullable=True)
    checkpoint = Column(String)
    status = Column(String)
    timestamp = Column(String, nullable=True)
    details = Column(String)

    hypothesis = relationship("HypothesisModel", back_populates="evidence_matrix")
