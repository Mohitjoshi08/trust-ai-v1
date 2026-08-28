from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class DetectionMethod(str, Enum):
    BSTS = "bsts"
    Z_SCORE = "z_score"
    CACHED = "cached"
    HARDCODED = "hardcoded"

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

class TimeSeriesResponse(BaseModel):
    data: List[TimeSeriesPoint]
    anomalies: List[AnomalyWindow]
    served_from: str
    detection_method: DetectionMethod

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

class ReconciliationResult(BaseModel):
    aggregate_delta: float
    explained_delta: float
    residual_delta: float
    explained_share: float
    status: str  # reconciled / partial / failed
    tolerance: float

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

class Hypothesis(BaseModel):
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
    # Backwards compatibility
    confidence_score: Optional[int] = None

class RecoveryValidation(BaseModel):
    detected: bool
    recovery_event_id: Optional[str] = None
    recovery_event_timestamp: Optional[datetime] = None
    metric_recovered: bool
    recovery_summary: str

class HypothesisResult(BaseModel):
    hypotheses: List[Hypothesis]
    served_from: str = "cache"
    status: str = "healthy"

class InvestigationReport(BaseModel):
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    reconciliation: Optional[ReconciliationResult] = None
    rag: RAGResult
    retrieval_metadata: Optional[RetrievalMetadata] = None
    timeline: List[EvidenceLink] = []
    hypotheses: List[Hypothesis] = []
    recovery_validation: Optional[RecoveryValidation] = None
    overall_status: str = "investigate"

class AnomalyReport(BaseModel):
    # Old compatibility container, but updated inner types
    anomaly_window: AnomalyWindow
    decomposition: DecompositionResult
    rag: RAGResult
    hypothesis: HypothesisResult
    investigation: Optional[InvestigationReport] = None

class FullTraceResponse(BaseModel):
    timeseries: TimeSeriesResponse
    reports: List[AnomalyReport]
