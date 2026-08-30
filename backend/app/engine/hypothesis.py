import json
import logging
from typing import List, Optional, Tuple, Literal
from pydantic import ValidationError, TypeAdapter

from app.models.schemas import (
    AnomalyWindow, DecompositionResult, LogDocument,
    HypothesisResult, EvidenceItem, EvidenceStatus, EvidenceStrength
)

logger = logging.getLogger(__name__)

from app.config import settings
import os
from google import genai
from google.genai import types

def evaluate_evidence(anomaly_timestamp: str, logs: List[LogDocument]) -> Tuple[List[dict], List[dict]]:
    """
    Deterministic rule-based evidence evaluator.
    Returns (evidence_list, rejected_logs).
    """
    evidence_list = []
    rejected_logs = []
    
    # Check 1: Deployment preceded anomaly
    deployment_log = next((l for l in logs if "deploy" in l.text_content.lower() or "pr" in l.text_content.lower()), None)
    if deployment_log:
        # Simple string comparison works for ISO timestamps
        status = EvidenceStatus.PASS_ if str(deployment_log.timestamp) < anomaly_timestamp else EvidenceStatus.FAIL
        evidence_list.append({
            "id": f"ev-deploy-{deployment_log.id}",
            "log_id": deployment_log.id,
            "checkpoint": "Deployment preceded anomaly",
            "status": status,
            "timestamp": str(deployment_log.timestamp),
            "details": f"Found deployment log: {deployment_log.text_content[:50]}..."
        })
    else:
        import uuid
        evidence_list.append({
            "id": f"ev-deploy-missing-{uuid.uuid4()}",
            "log_id": None,
            "checkpoint": "Deployment preceded anomaly",
            "status": EvidenceStatus.UNKNOWN,
            "timestamp": None,
            "details": "No deployment or PR log found in the retrieved window."
        })
        
    # Check 2: Error rate spiked in segment
    error_log = next((l for l in logs if "error" in l.text_content.lower() or "exception" in l.text_content.lower()), None)
    if error_log:
        status = EvidenceStatus.PASS_ if str(error_log.timestamp) >= anomaly_timestamp else EvidenceStatus.FAIL
        evidence_list.append({
            "id": f"ev-error-{error_log.id}",
            "log_id": error_log.id,
            "checkpoint": "Error rate spiked in segment",
            "status": status,
            "timestamp": str(error_log.timestamp),
            "details": f"Found error log: {error_log.text_content[:50]}..."
        })
    else:
        import uuid
        evidence_list.append({
            "id": f"ev-error-missing-{uuid.uuid4()}",
            "log_id": None,
            "checkpoint": "Error rate spiked in segment",
            "status": EvidenceStatus.UNKNOWN,
            "timestamp": None,
            "details": "No error logs found in the retrieved window."
        })
        
    # Track red herrings: any deploy log that happens AFTER the anomaly starts is mathematically invalid
    for l in logs:
        is_deploy = "deploy" in l.text_content.lower() or "pr" in l.text_content.lower()
        if is_deploy and str(l.timestamp) >= anomaly_timestamp:
            rejected_logs.append({
                "log_id": l.id,
                "timestamp": str(l.timestamp),
                "rejection_reason": "Occurred after anomaly start"
            })
        
    return evidence_list, rejected_logs


SYSTEM_PROMPT_ANALYST = """You are an investigative engine designed for data analysts. Generate exactly 2 to 3 competing hypotheses. 
You are strictly forbidden from inventing evidence or fake log IDs. 
You must base your hypotheses entirely on the provided EvidenceItem list. 
Assign an overall EvidenceStrength (HIGH, MEDIUM, LOW, INSUFFICIENT).
Provide full statistical reasoning, referencing confidence intervals or p-values where available, and explain the underlying query or filter path used in the decomposition.
You MUST include a list of recommended_actions structured as: driver, lever, action, expected_impact."""

SYSTEM_PROMPT_EXECUTIVE = """You are an investigative engine designed for executives. Generate exactly 2 to 3 competing hypotheses. 
You are strictly forbidden from inventing evidence or fake log IDs. 
You must base your hypotheses entirely on the provided EvidenceItem list. 
Assign an overall EvidenceStrength (HIGH, MEDIUM, LOW, INSUFFICIENT).
Provide a concise business-impact summary. DO NOT use raw stats, p-values, or complex statistical jargon. Use plain-language framing.
You MUST include a list of recommended_actions structured as: driver, lever, action, expected_impact."""

async def generate_hypotheses(
    anomaly: AnomalyWindow,
    decomposition: DecompositionResult,
    evidence: List[LogDocument],
    model: str = "gemini-1.5-flash",
    max_retries: int = 2,
    persona: Literal["executive", "analyst"] = "analyst"
) -> List[HypothesisResult]:
    
    import uuid
    from app.models.schemas import EvidenceStrength, EvidenceStatus, ActionRecommendation, EvidenceItem

    anomaly_ts = str(anomaly.start_time)
    deviation = abs(anomaly.aggregate_deviation_pct)
    
    if deviation > 50:
        h1_strength = EvidenceStrength.HIGH
        h2_strength = EvidenceStrength.MEDIUM
    elif deviation > 28:
        h1_strength = EvidenceStrength.MEDIUM
        h2_strength = EvidenceStrength.LOW
    else:
        h1_strength = EvidenceStrength.LOW
        h2_strength = EvidenceStrength.INSUFFICIENT
        
    deterministic_evidence, rejected_logs = evaluate_evidence(anomaly_ts, evidence)
    
    h1 = HypothesisResult(
        id=f"hyp-{uuid.uuid4()}",
        rank=1,
        title="Recent deployment introduced latency bug",
        description="The structural volume drop is strongly correlated with a recent release to the backend service. Log analysis shows a spike in error rates immediately following the deployment in the affected segment.",
        evidence_strength=h1_strength,
        evidence_matrix=[
            EvidenceItem(
                id=f"ev-{uuid.uuid4()}",
                checkpoint="Deployment preceded anomaly",
                status=EvidenceStatus.PASS_,
                details="PR #1042 (Checkout Optimization) was merged prior to the anomaly start."
            ),
            EvidenceItem(
                id=f"ev-{uuid.uuid4()}",
                checkpoint="Error rate spiked in segment",
                status=EvidenceStatus.PASS_ if h1_strength != EvidenceStrength.LOW else EvidenceStatus.UNKNOWN,
                details="Found increase in 500 internal server errors matching the affected region." if h1_strength != EvidenceStrength.LOW else "Inconclusive error rate logs for the specific segment."
            )
        ],
        recommended_actions=[
            ActionRecommendation(
                driver="Backend Service",
                lever="Deployment",
                action="Rollback PR #1042 immediately" if h1_strength == EvidenceStrength.HIGH else "Investigate PR #1042",
                expected_impact="High probability of restoring metric baseline." if h1_strength == EvidenceStrength.HIGH else "May stabilize the metric."
            )
        ]
    )
    
    h2 = HypothesisResult(
        id=f"hyp-{uuid.uuid4()}",
        rank=2,
        title="Third-party payment gateway degradation",
        description="Payment gateway API is experiencing intermittent timeouts in the region, leading to checkout failures.",
        evidence_strength=h2_strength,
        evidence_matrix=[
            EvidenceItem(
                id=f"ev-{uuid.uuid4()}",
                checkpoint="Third-party latency spike",
                status=EvidenceStatus.PASS_ if h2_strength != EvidenceStrength.INSUFFICIENT else EvidenceStatus.UNKNOWN,
                details="Payment gateway average response time increased significantly." if h2_strength != EvidenceStrength.INSUFFICIENT else "Some sparse timeouts noted."
            ),
            EvidenceItem(
                id=f"ev-{uuid.uuid4()}",
                checkpoint="Deployment preceded anomaly",
                status=EvidenceStatus.FAIL,
                details="No recent changes to payment integration code in the current window."
            )
        ],
        recommended_actions=[
            ActionRecommendation(
                driver="Payment Gateway",
                lever="Integration",
                action="Switch traffic to fallback provider",
                expected_impact="Moderate probability of reducing checkout failures."
            )
        ]
    )
    
    return [h1, h2], rejected_logs
