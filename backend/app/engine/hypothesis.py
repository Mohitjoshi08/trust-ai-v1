import json
import logging
from typing import List, Optional
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.models.schemas import (
    AnomalyWindow, DecompositionResult, LogDocument,
    Hypothesis, HypothesisResult, EvidenceCheck
)

logger = logging.getLogger(__name__)

from app.config import settings
import os

api_key = os.environ.get("OPENAI_API_KEY") or settings.GEMINI_API_KEY or "dummy_key"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if not os.environ.get("OPENAI_API_KEY") else None

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

SYSTEM_PROMPT = """You are a Root Cause Analysis engine for business metrics.

You will receive:
1. METRIC DATA: A statistical anomaly with the exact affected segment.
2. EVIDENCE LOGS: Operational documents from the exact time window.

Your task:
- Evaluate whether the evidence logs explain the metric anomaly.
- Output ranked hypotheses as JSON.
- Each hypothesis MUST cite specific evidence IDs.
- Replace probability percentages with evidence strength: HIGH, MEDIUM, LOW, INSUFFICIENT.
- Include an internal evidence_score (0-100) for ranking, but DO NOT present it as a probability.
- Provide a list of 'evidence_checks' (e.g., temporal_alignment, affected_segment_match, operational_confirmation).
- Set the status to one of: 'recommended', 'investigate', 'rejected', 'ambiguous'.

CALIBRATION RULES:
- A score of 90+ requires: (a) a code change or deployment logged BEFORE the anomaly start,
  (b) user-facing symptoms logged AFTER, and (c) the affected segment matches.
- A score of 70+ requires at least 2 of the 3 conditions above.
- If only 1 condition is met, the score MUST be below 50.
- Do NOT cluster all scores between 80-90. Use the full range.

CRITICAL RULES:
- Do NOT invent evidence. Only cite provided document IDs.
- Do NOT confuse correlation with causation.
- If no evidence explains the anomaly, output a single hypothesis with
  cause_title "Insufficient evidence" and evidence_score 0.
"""

def build_repair_prompt(original_prompt: str, error: str, bad_output: str) -> str:
    return f"""The previous output failed validation with the following error:
{error}

Previous output:
{bad_output}

Please fix the output to strictly conform to the requested JSON schema.
"""

async def generate_hypotheses(
    anomaly: AnomalyWindow,
    decomposition: DecompositionResult,
    evidence: List[LogDocument],
    model: str = "gemini-1.5-flash" if "generativelanguage" in str(client.base_url) else "gpt-4o",
    max_retries: int = 2
) -> HypothesisResult:
    
    prompt = f"Anomaly: {anomaly.metric_name} {anomaly.direction} by {abs(anomaly.aggregate_deviation_pct)}%.\n"
    prompt += f"Primary Driver: {decomposition.primary_driver.dimension} = {decomposition.primary_driver.segment_value}\n\n"
    prompt += "Retrieved Logs:\n"
    for log in evidence:
        prompt += f"- [{log.id}] ({log.source}): {log.text_content}\n"
        
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=messages,
                temperature=0.2
            )
            raw_content = response.choices[0].message.content
            raw = json.loads(raw_content)
            
            # Validate against Pydantic schema
            # We expect a dict with 'hypotheses' array
            result = HypothesisResult.model_validate(raw)
            
            # Post-validation: check for hallucinated evidence IDs
            valid_ids = {e.id for e in evidence}
            for hyp in result.hypotheses:
                hyp.supporting_evidence_ids = [
                    eid for eid in hyp.supporting_evidence_ids if eid in valid_ids
                ]
                # If all cited evidence was hallucinated, drop confidence/score
                if not hyp.supporting_evidence_ids and hyp.evidence_score > 15:
                    hyp.evidence_score = min(hyp.evidence_score, 15)
                    hyp.reasoning += " [Warning: original citations could not be verified]"
                    hyp.evidence_strength = "INSUFFICIENT"
                    
            result.served_from = "gpt-4o"
            result.status = "healthy"
            return result
            
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt < max_retries:
                # Re-prompt with the error message for self-correction
                repair_prompt = build_repair_prompt(
                    original_prompt=prompt,
                    error=str(e),
                    bad_output=raw_content if 'raw_content' in locals() else ""
                )
                messages.append({"role": "assistant", "content": raw_content if 'raw_content' in locals() else "{}"})
                messages.append({"role": "user", "content": repair_prompt})
                continue
            else:
                break
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            break
            
    # Final fallback
    return HypothesisResult(
        hypotheses=[Hypothesis(
            rank=1,
            cause_title="Analysis inconclusive",
            evidence_strength="INSUFFICIENT",
            evidence_score=0,
            reasoning="The system was unable to generate a valid analysis. Please review the evidence logs manually.",
            supporting_evidence_ids=[],
            evidence_checks=[],
            recommended_action="Manual review of operational logs for the anomaly window.",
            status="investigate"
        )],
        served_from="fallback",
        status="error"
    )
