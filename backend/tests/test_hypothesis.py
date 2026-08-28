"""
Trace.ai — Hypothesis Engine Tests
"""
import pytest
import asyncio
from datetime import datetime
from app.models.schemas import (
    AnomalyWindow, DecompositionResult, SegmentContribution, 
    LogDocument, DetectionMethod, HypothesisResult, Hypothesis
)
from app.engine.hypothesis import generate_hypotheses

class MockChoice:
    def __init__(self, content):
        self.message = type('obj', (object,), {'content': content})

class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockAsyncCompletions:
    def __init__(self):
        self.call_count = 0
        self.last_messages = []
        
    async def create(self, **kwargs):
        self.call_count += 1
        self.last_messages = kwargs.get("messages", [])
        
        # Test 1: Malformed JSON on first try, fixed on second
        if "bad_json" in self.last_messages[1]["content"]:
            if self.call_count == 1:
                return MockResponse("{ bad json }")
            else:
                return MockResponse('{"hypotheses": [{"rank": 1, "cause_title": "Fixed", "evidence_strength": "HIGH", "evidence_score": 90, "reasoning": "Fixed JSON", "supporting_evidence_ids": ["log1"], "recommended_action": "None", "status": "recommended"}]}')
                
        # Test 2: Hallucinated IDs
        if "hallucinate" in self.last_messages[1]["content"]:
            return MockResponse('{"hypotheses": [{"rank": 1, "cause_title": "Hallucinated", "evidence_strength": "HIGH", "evidence_score": 90, "reasoning": "Hallucinated ID", "supporting_evidence_ids": ["fake_id_123"], "recommended_action": "None", "status": "recommended"}]}')
            
        # Default success
        return MockResponse('{"hypotheses": [{"rank": 1, "cause_title": "Valid", "evidence_strength": "HIGH", "evidence_score": 90, "reasoning": "Valid output", "supporting_evidence_ids": ["log1"], "recommended_action": "None", "status": "recommended"}]}')

@pytest.fixture
def dummy_data():
    anomaly = AnomalyWindow(
        start_time=datetime(2025, 8, 5), end_time=datetime(2025, 8, 7),
        severity=3.0, direction="drop", metric_name="revenue",
        aggregate_actual_mean=100, aggregate_expected_mean=200, aggregate_deviation_pct=-50,
        detection_method=DetectionMethod.BSTS
    )
    seg1 = SegmentContribution(
        dimension="device", segment_value="iOS", baseline_mean=100, anomaly_mean=50, 
        absolute_change=-50, segment_percent_change=-50, contribution_amount=1, contribution_share_of_aggregate=100, contribution_to_total=100
    )
    decomp = DecompositionResult(
        anomaly_window=anomaly,
        primary_driver=seg1,
        is_ambiguous=False,
        level2_drilldowns=[],
        all_segments=[seg1],
        drill_down_paths=[]
    )
    
    logs = [
        LogDocument(id="log1", timestamp=datetime(2025, 8, 4), source="github", text_content="PR merged", similarity_score=0.9, matched_query="")
    ]
    
    return anomaly, decomp, logs

@pytest.mark.asyncio
async def test_hypothesis_valid_output(dummy_data, monkeypatch):
    import app.engine.hypothesis as hyp_module
    
    mock_client = type('obj', (object,), {'chat': type('obj', (object,), {'completions': MockAsyncCompletions()})})
    monkeypatch.setattr(hyp_module, "client", mock_client)
    
    anomaly, decomp, logs = dummy_data
    result = await generate_hypotheses(anomaly, decomp, logs)
    
    assert isinstance(result, HypothesisResult)
    assert result.hypotheses[0].cause_title == "Valid"
    assert "log1" in result.hypotheses[0].supporting_evidence_ids

@pytest.mark.asyncio
async def test_hypothesis_malformed_json_retry(dummy_data, monkeypatch):
    import app.engine.hypothesis as hyp_module
    
    mock_client = type('obj', (object,), {'chat': type('obj', (object,), {'completions': MockAsyncCompletions()})})
    monkeypatch.setattr(hyp_module, "client", mock_client)
    
    anomaly, decomp, logs = dummy_data
    anomaly.metric_name = "bad_json" # Trigger the mock condition
    
    result = await generate_hypotheses(anomaly, decomp, logs)
    
    assert mock_client.chat.completions.call_count == 2
    assert result.hypotheses[0].cause_title == "Fixed"

@pytest.mark.asyncio
async def test_hypothesis_hallucination_stripping(dummy_data, monkeypatch):
    import app.engine.hypothesis as hyp_module
    
    mock_client = type('obj', (object,), {'chat': type('obj', (object,), {'completions': MockAsyncCompletions()})})
    monkeypatch.setattr(hyp_module, "client", mock_client)
    
    anomaly, decomp, logs = dummy_data
    anomaly.metric_name = "hallucinate" # Trigger the mock condition
    
    result = await generate_hypotheses(anomaly, decomp, logs)
    
    # ID should be stripped, score should drop to <= 15
    assert len(result.hypotheses[0].supporting_evidence_ids) == 0
    assert result.hypotheses[0].evidence_score <= 15
    assert "Warning" in result.hypotheses[0].reasoning
