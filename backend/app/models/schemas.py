from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


# ============================================================
# Core Enums
# ============================================================

class DetectionMethod(str, Enum):
    BSTS = "bsts"
    Z_SCORE = "z_score"
    CACHED = "cached"
    HARDCODED = "hardcoded"
    RULE_BASED = "rule_based"


class EvidenceStatus(str, Enum):
    """Status of an individual evidence checkpoint."""
    PASS_ = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(str, Enum):
    """Qualitative strength of the evidence supporting a hypothesis."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


# ============================================================
# Time-Series & Anomaly Models (unchanged)
# ============================================================

class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    actual: float
    predicted_mean: float
    upper_bound: float
    lower_bound: float

class AnomalyWindow(BaseModel):
    start_time: datetime
    end_time: datetime
    severity: float
    direction: str
    metric_name: str
    aggregate_actual_mean: float
    aggregate_expected_mean: float
    aggregate_deviation_pct: float
    detection_method: DetectionMethod
    anomaly_type: str = "Standard"

class TimeSeriesResponse(BaseModel):
    data: List[TimeSeriesPoint]
    anomalies: List[AnomalyWindow]
    served_from: str
    detection_method: DetectionMethod


# ============================================================
# Decomposition Models (unchanged)
# ============================================================

class SegmentContribution(BaseModel):
    dimension: str
    segment_value: str
    baseline_mean: float
    anomaly_mean: float
    absolute_change: float
    segment_percent_change: float
    contribution_amount: float = 0.0
    contribution_share_of_aggregate: float = 0.0
    contribution_to_total: Optional[float] = None  # Backwards compatibility

class Level2DrillDown(BaseModel):
    parent_segment: str
    sub_dimension: str
    is_uniform: bool
    dominant_subsegment: Optional[str]
    sub_contributions: List[SegmentContribution] = []

class DecompositionResult(BaseModel):
    anomaly_window: AnomalyWindow
    primary_driver: SegmentContribution
    secondary_driver: Optional[SegmentContribution] = None
    is_ambiguous: bool
    level2_drilldowns: List[Level2DrillDown]
    all_segments: List[SegmentContribution]
    drill_down_paths: List[List[str]]
    reconciliation: Optional['ReconciliationResult'] = None

class ReconciliationResult(BaseModel):
    aggregate_delta: float
    explained_delta: float
    residual_delta: float
    explained_share: float
    status: str  # reconciled / partial / failed
    tolerance: float


# ============================================================
# RAG / Log Models (unchanged)
# ============================================================

class LogDocument(BaseModel):
    id: str
    timestamp: datetime
    source: str
    text_content: str
    similarity_score: float
    matched_query: str = ""

class RAGResult(BaseModel):
    decomposition: DecompositionResult
    search_queries: List[str]
    retrieved_logs: List[LogDocument]

class RetrievalMetadata(BaseModel):
    initial_window_start: datetime
    initial_window_end: datetime
    final_window_start: datetime
    final_window_end: datetime
    expansion_steps: int
    evidence_sufficient: bool

class EvidenceLink(BaseModel):
    id: str
    timestamp: datetime
    source: str
    excerpt: str
    relevance_score: float
    role: str  # temporal / symptom / deployment / incident / recovery / contradiction


# ============================================================
# Phase 2: Evidence Matrix & Multi-Hypothesis Models (NEW)
# ============================================================

class EvidenceItem(BaseModel):
    """A single checkpoint in the evidence matrix for a hypothesis."""
    id: str
    log_id: Optional[str] = None
    checkpoint: str  # e.g., "Deployment preceded anomaly"
    status: EvidenceStatus
    timestamp: Optional[str] = None
    details: str

class ActionRecommendation(BaseModel):
    driver: str
    lever: str
    action: str
    expected_impact: str


class HypothesisResult(BaseModel):
    """
    Phase 2 hypothesis result — a single competing hypothesis with
    a structured evidence matrix (replaces raw confidence scores).
    """
    id: str
    rank: int
    title: str
    description: str
    evidence_strength: EvidenceStrength
    evidence_matrix: List[EvidenceItem]
    recommended_actions: List[ActionRecommendation] = []
    analyst_feedback: Optional[bool] = None

class RejectedLog(BaseModel):
    log_id: str
    timestamp: str
    rejection_reason: str


# ============================================================
# Legacy V1 Hypothesis Models (kept for hypothesis.py compat)
# ============================================================

class EvidenceCheck(BaseModel):
    check_name: str
    result: str  # pass / fail / unknown
    explanation: str
    weight: float

class EvidenceMatrix(BaseModel):
    hypothesis_id: str
    checks: List[EvidenceCheck]
    passed_count: int
    failed_count: int
    unknown_count: int

class HypothesisV1(BaseModel):
    """
    Legacy hypothesis model (V1). Used by hypothesis.py engine and its tests.
    The deprecated confidence_score field has been removed.
    """
    rank: int
    cause_title: str
    evidence_strength: str   # HIGH / MEDIUM / LOW / INSUFFICIENT
    evidence_score: int      # 0-100 internal score; NOT a probability
    reasoning: str
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str] = []
    evidence_checks: List[EvidenceCheck] = []
    recommended_action: str
    status: str = "investigate"  # recommended / investigate / rejected / ambiguous

# Backward-compatibility alias so `from app.models.schemas import Hypothesis` still works
Hypothesis = HypothesisV1

class RecoveryValidation(BaseModel):
    detected: bool
    recovery_event_id: Optional[str] = None
    recovery_event_timestamp: Optional[datetime] = None
    metric_recovered: bool
    recovery_summary: str

class HypothesisResultV1(BaseModel):
    """
    Legacy wrapper around a list of V1 hypotheses.
    Used for parsing the old 'hypothesis' key in golden cache.
    """
    hypotheses: List[HypothesisV1]
    served_from: str = "cache"
    status: str = "healthy"

class InvestigationReport(BaseModel):
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    reconciliation: Optional[ReconciliationResult] = None
    rag: RAGResult
    retrieval_metadata: Optional[RetrievalMetadata] = None
    timeline: List[EvidenceLink] = []
    hypotheses: List[HypothesisV1] = []
    recovery_validation: Optional[RecoveryValidation] = None
    overall_status: str = "investigate"


# ============================================================
# Top-Level Report & Response Models
# ============================================================

class AnomalyReport(BaseModel):
    """
    Top-level report for a single anomaly.

    Phase 2: The primary data contract now uses `hypotheses` —
    a list of 2-3 competing HypothesisResult objects with structured
    evidence matrices. The old `hypothesis` (HypothesisResultV1 wrapper)
    is retained as Optional for backward-compatible cache parsing.
    """
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    rag: RAGResult
    # Phase 2: structured multi-hypothesis list
    hypotheses: List[HypothesisResult] = []
    # Legacy: old hypothesis wrapper (optional, for cache parsing)
    hypothesis: Optional[HypothesisResultV1] = None
    investigation: Optional[InvestigationReport] = None
    recovered: Optional[bool] = None
    rejected_logs: List[RejectedLog] = []

class FullTraceResponse(BaseModel):
    timeseries: TimeSeriesResponse
    reports: List[AnomalyReport]

class RegenerateRequest(BaseModel):
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    retrieved_logs: List[LogDocument]
    persona: str = "analyst"
