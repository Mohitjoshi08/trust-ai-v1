import json
import logging
from typing import List, Optional, Tuple
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
        evidence_list.append({
            "id": "ev-deploy-missing",
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
        evidence_list.append({
            "id": "ev-error-missing",
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


SYSTEM_PROMPT = """You are an investigative engine. Generate exactly 2 to 3 competing hypotheses. 
You are strictly forbidden from inventing evidence or fake log IDs. 
You must base your hypotheses entirely on the provided EvidenceItem list. 
Assign an overall EvidenceStrength (HIGH, MEDIUM, LOW, INSUFFICIENT)."""

async def generate_hypotheses(
    anomaly: AnomalyWindow,
    decomposition: DecompositionResult,
    evidence: List[LogDocument],
    model: str = "gemini-1.5-flash",
    max_retries: int = 2
) -> List[HypothesisResult]:
    
    api_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or "dummy_key"
    client = genai.Client(api_key=api_key)
    
    anomaly_ts = str(anomaly.start_time)
    deterministic_evidence, rejected_logs = evaluate_evidence(anomaly_ts, evidence)
    
    prompt = f"Anomaly: {anomaly.metric_name} {anomaly.direction} by {abs(anomaly.aggregate_deviation_pct)}%.\n"
    prompt += f"Primary Driver: {decomposition.primary_driver.dimension} = {decomposition.primary_driver.segment_value}\n\n"
    prompt += "Deterministic EvidenceItems:\n"
    prompt += json.dumps(deterministic_evidence, indent=2)
    
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=list[HypothesisResult],
                    temperature=0.2
                )
            )
            
            raw = json.loads(response.text)
            adapter = TypeAdapter(List[HypothesisResult])
            result = adapter.validate_python(raw)
            return result, rejected_logs
            
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            if attempt == max_retries:
                break
            
    import uuid
    # Final fallback
    fallback = HypothesisResult(
        id=f"hyp-fallback-{uuid.uuid4()}",
        rank=1,
        title="Analysis inconclusive",
        description="The system was unable to generate a valid analysis. Please review the evidence logs manually.",
        evidence_strength=EvidenceStrength.INSUFFICIENT,
        evidence_matrix=[]
    )
    return [fallback], rejected_logs
