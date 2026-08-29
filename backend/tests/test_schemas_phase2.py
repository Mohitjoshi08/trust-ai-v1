"""
Phase 2 Schema Validation Tests.

Validates that:
1. All new Pydantic models instantiate cleanly.
2. Golden cache payloads parse without ValidationError.
3. The AnomalyReport model correctly holds both old and new hypothesis formats.
"""
import json
import os
import pytest
from datetime import datetime

from app.models.schemas import (
    # New Phase 2 models
    EvidenceStatus,
    EvidenceStrength,
    EvidenceItem,
    HypothesisResult,
    # Legacy models (backward compat)
    Hypothesis,
    HypothesisV1,
    HypothesisResultV1,
    EvidenceCheck,
    # Structural models
    AnomalyReport,
    AnomalyWindow,
    DecompositionResult,
    SegmentContribution,
    RAGResult,
    LogDocument,
    DetectionMethod,
    TimeSeriesResponse,
    FullTraceResponse,
)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "golden_cache")


# ── Unit Tests: New Models ────────────────────────────────────

class TestEvidenceStatus:
    def test_enum_values(self):
        assert EvidenceStatus.PASS_ == "PASS"
        assert EvidenceStatus.FAIL == "FAIL"
        assert EvidenceStatus.UNKNOWN == "UNKNOWN"


class TestEvidenceStrength:
    def test_enum_values(self):
        assert EvidenceStrength.HIGH == "HIGH"
        assert EvidenceStrength.MEDIUM == "MEDIUM"
        assert EvidenceStrength.LOW == "LOW"
        assert EvidenceStrength.INSUFFICIENT == "INSUFFICIENT"


class TestEvidenceItem:
    def test_minimal(self):
        item = EvidenceItem(
            id="ev-001",
            checkpoint="Deployment preceded anomaly",
            status=EvidenceStatus.PASS_,
            details="PR merged before anomaly start."
        )
        assert item.log_id is None
        assert item.timestamp is None
        assert item.status == EvidenceStatus.PASS_

    def test_full(self):
        item = EvidenceItem(
            id="ev-002",
            log_id="abc-123",
            checkpoint="Error rate spiked in segment",
            status=EvidenceStatus.FAIL,
            timestamp="2025-06-10T16:45:00",
            details="No error spike observed."
        )
        assert item.log_id == "abc-123"
        assert item.status == EvidenceStatus.FAIL


class TestHypothesisResult:
    def test_instantiation(self):
        result = HypothesisResult(
            id="hyp-001",
            rank=1,
            title="Stripe SDK Failure",
            description="A deployment broke the iOS checkout.",
            evidence_strength=EvidenceStrength.HIGH,
            evidence_matrix=[
                EvidenceItem(
                    id="ev-001",
                    checkpoint="Deployment preceded anomaly",
                    status=EvidenceStatus.PASS_,
                    details="PR merged before anomaly."
                ),
                EvidenceItem(
                    id="ev-002",
                    checkpoint="Segment matches driver",
                    status=EvidenceStatus.PASS_,
                    details="iOS is primary driver."
                ),
            ]
        )
        assert result.rank == 1
        assert len(result.evidence_matrix) == 2
        assert result.evidence_strength == EvidenceStrength.HIGH


class TestBackwardCompat:
    def test_hypothesis_alias(self):
        """Hypothesis should still be importable and equal to HypothesisV1."""
        assert Hypothesis is HypothesisV1

    def test_hypothesis_v1_no_confidence_score(self):
        """V1 model should work without the removed confidence_score field."""
        hyp = HypothesisV1(
            rank=1,
            cause_title="Test",
            evidence_strength="HIGH",
            evidence_score=90,
            reasoning="Test reasoning",
            supporting_evidence_ids=["log1"],
            recommended_action="Fix it",
            status="recommended"
        )
        assert hyp.rank == 1
        assert not hasattr(hyp, "confidence_score") or hyp.model_fields.get("confidence_score") is None

    def test_hypothesis_result_v1_wrapper(self):
        """Old HypothesisResultV1 wrapper should parse a list of V1 hypotheses."""
        wrapper = HypothesisResultV1(
            hypotheses=[
                HypothesisV1(
                    rank=1,
                    cause_title="Test",
                    evidence_strength="HIGH",
                    evidence_score=90,
                    reasoning="Test",
                    supporting_evidence_ids=[],
                    recommended_action="None",
                )
            ],
            served_from="cache",
            status="healthy"
        )
        assert len(wrapper.hypotheses) == 1


# ── Integration Tests: Golden Cache ────────────────────────────

class TestGoldenCacheHypothesisResults:
    def test_parse_hypothesis_results_json(self):
        """hypothesis_results.json should parse as a list of new HypothesisResult."""
        path = os.path.join(CACHE_DIR, "hypothesis_results.json")
        with open(path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) >= 2, "Should have at least 2 competing hypotheses"

        for i, h in enumerate(data):
            result = HypothesisResult.model_validate(h)
            assert result.id, f"Hypothesis {i} missing id"
            assert result.title, f"Hypothesis {i} missing title"
            assert len(result.evidence_matrix) > 0, f"Hypothesis {i} has empty evidence_matrix"


class TestGoldenCacheAnomalyReports:
    @pytest.fixture(scope="class")
    def reports_data(self):
        path = os.path.join(CACHE_DIR, "anomaly_reports.json")
        with open(path) as f:
            return json.load(f)

    def test_all_reports_have_new_hypotheses(self, reports_data):
        """Every report should have a non-empty 'hypotheses' array."""
        for i, r in enumerate(reports_data):
            hyps = r.get("hypotheses", [])
            assert len(hyps) > 0, f"Report {i} has no new hypotheses"
            assert len(hyps) <= 3, f"Report {i} has {len(hyps)} hypotheses (expected 2-3)"

    def test_new_hypotheses_validate(self, reports_data):
        """All new hypotheses should validate against HypothesisResult."""
        for i, r in enumerate(reports_data):
            for j, h in enumerate(r.get("hypotheses", [])):
                result = HypothesisResult.model_validate(h)
                assert result.evidence_strength in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")

    def test_old_hypothesis_wrapper_validates(self, reports_data):
        """Old hypothesis wrapper should still validate as HypothesisResultV1."""
        for i, r in enumerate(reports_data):
            old = r.get("hypothesis")
            if old:
                wrapper = HypothesisResultV1.model_validate(old)
                assert wrapper.served_from
                assert wrapper.status

    def test_full_anomaly_report_construction(self, reports_data):
        """Full AnomalyReport model should construct cleanly from cache data."""
        for i, r in enumerate(reports_data):
            new_hypotheses = [HypothesisResult(**h) for h in r.get("hypotheses", [])]
            old_hypothesis = HypothesisResultV1(**r["hypothesis"]) if r.get("hypothesis") else None

            report = AnomalyReport(
                anomaly_window=AnomalyWindow(**r["decomposition"]["anomaly_window"]),
                decomposition=DecompositionResult(**r["decomposition"]),
                rag=RAGResult(**r["rag"]),
                hypotheses=new_hypotheses,
                hypothesis=old_hypothesis,
            )
            assert len(report.hypotheses) > 0
            assert report.anomaly_window.metric_name == "revenue"


class TestNoConfidenceScore:
    def test_confidence_score_removed_from_cache(self):
        """The deprecated confidence_score should be absent from the old hypothesis wrapper."""
        path = os.path.join(CACHE_DIR, "anomaly_reports.json")
        with open(path) as f:
            data = json.load(f)

        for i, r in enumerate(data):
            for j, h in enumerate(r.get("hypothesis", {}).get("hypotheses", [])):
                assert "confidence_score" not in h, (
                    f"Report {i} hypothesis {j} still has deprecated confidence_score"
                )
