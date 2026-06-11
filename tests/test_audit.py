import csv
import io
import os
import random
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.domain.enums import ScreeningStatus, SourceType
from src.domain.metrics import (
    ConfusionMatrix,
    compute_confusion_matrix,
    compute_metrics,
    metrics_to_dict,
)
from src.domain.models import Paper, ScreeningDecision

client = TestClient(app)

CSV_ROWS = 10
CSV_CONTENT = "\n".join(
    [
        "Global_ID,Title,Abstract,Provenance_Trace",
        *[f"T{i},Paper {i},Abstract {i},wl:acm" for i in range(1, CSV_ROWS + 1)],
    ]
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_global_state():
    from src.api import routes
    routes._dataset_path = None
    routes._screening_active = False
    routes._imported_count = 0
    yield


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    from src.api import routes

    import_dir = tmp_path / "imported"
    process_dir = tmp_path / "processed"
    import_dir.mkdir()
    process_dir.mkdir()
    db_path = str(tmp_path / "screening.db")

    monkeypatch.setattr(routes, "_IMPORT_DIR", import_dir)
    monkeypatch.setattr(routes, "_PROCESSED_DIR", process_dir)
    monkeypatch.setenv("APOLLO_DB_PATH", db_path)

    return tmp_path


@pytest.fixture
def imported_env(test_env):
    """Import CSV and add screening decisions for all 10 papers."""
    client.post(
        "/api/import",
        files={"file": ("test.csv", CSV_CONTENT, "text/csv")},
    )
    from src.api.routes import _get_decision_repo
    repo = _get_decision_repo()
    for i in range(1, CSV_ROWS + 1):
        status = (
            ScreeningStatus.INCLUDED
            if i <= 3
            else ScreeningStatus.EXCLUDED
            if i <= 8
            else ScreeningStatus.NEEDS_REVIEW
        )
        repo.save_decision(ScreeningDecision(
            paper_id=f"T{i}",
            status=status,
            confidence_score=0.9,
            rationale=f"Rationale for paper {i}",
            applied_criteria_codes=["IC1"] if status == ScreeningStatus.INCLUDED else ["EC4"] if i < 7 else [],
        ))
    return test_env


# ═══════════════════════════════════════════════════════════════════════════════
# Unit: Confusion Matrix
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfusionMatrix:
    def test_perfect_agreement(self):
        ai = ["YES", "YES", "NO", "NO"]
        hu = ["YES", "YES", "NO", "NO"]
        cm = compute_confusion_matrix(ai, hu)
        assert cm == ConfusionMatrix(tp=2, tn=2, fp=0, fn=0)

    def test_no_agreement(self):
        ai = ["YES", "YES", "NO", "NO"]
        hu = ["NO", "NO", "YES", "YES"]
        cm = compute_confusion_matrix(ai, hu)
        assert cm == ConfusionMatrix(tp=0, tn=0, fp=2, fn=2)

    def test_partial_agreement(self):
        ai = ["YES", "YES", "YES", "NO", "NO", "NO", "NO", "NO", "NO", "NO"]
        hu = ["YES", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "YES"]
        cm = compute_confusion_matrix(ai, hu)
        assert cm == ConfusionMatrix(tp=1, tn=6, fp=2, fn=1)

    def test_empty_lists(self):
        cm = compute_confusion_matrix([], [])
        assert cm == ConfusionMatrix(tp=0, tn=0, fp=0, fn=0)

    def test_all_positive(self):
        ai = ["YES", "YES", "YES"]
        hu = ["YES", "YES", "YES"]
        cm = compute_confusion_matrix(ai, hu)
        assert cm == ConfusionMatrix(tp=3, tn=0, fp=0, fn=0)

    def test_all_negative(self):
        ai = ["NO", "NO", "NO"]
        hu = ["NO", "NO", "NO"]
        cm = compute_confusion_matrix(ai, hu)
        assert cm == ConfusionMatrix(tp=0, tn=3, fp=0, fn=0)


# ═══════════════════════════════════════════════════════════════════════════════
# Unit: Metrics (Precision, Recall, F1, Cohen's Kappa)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetrics:
    def test_perfect_metrics(self):
        ai = ["YES", "YES", "NO", "NO"]
        hu = ["YES", "YES", "NO", "NO"]
        m = compute_metrics(ai, hu)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1_score == 1.0
        assert m.cohens_kappa == 1.0
        assert "Almost perfect" in m.interpretation

    def test_random_agreement_kappa_zero(self):
        ai = ["YES", "YES", "NO", "NO"]
        hu = ["YES", "NO", "YES", "NO"]
        m = compute_metrics(ai, hu)
        assert m.precision == 0.5
        assert m.recall == 0.5
        assert m.f1_score == 0.5
        assert m.cohens_kappa == 0.0
        assert "Poor" in m.interpretation

    def test_inverse_agreement_kappa_negative(self):
        ai = ["YES", "YES", "NO", "NO"]
        hu = ["NO", "NO", "YES", "YES"]
        m = compute_metrics(ai, hu)
        assert m.cohens_kappa < 0

    def test_mixed_metrics_known_values(self):
        ai = ["YES", "YES", "YES", "NO", "NO", "NO", "NO", "NO", "NO", "NO"]
        hu = ["YES", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "YES"]
        m = compute_metrics(ai, hu)
        # TP=1, TN=6, FP=2, FN=1
        assert m.confusion_matrix.tp == 1
        assert m.confusion_matrix.tn == 6
        assert m.confusion_matrix.fp == 2
        assert m.confusion_matrix.fn == 1
        # Precision = 1/3, Recall = 1/2, F1 = 0.4
        assert m.precision == pytest.approx(1 / 3, abs=1e-4)
        assert m.recall == 0.5
        assert m.f1_score == pytest.approx(0.4, abs=1e-4)
        # Po = 7/10 = 0.7
        # Pe = 0.3*0.2 + 0.7*0.8 = 0.06 + 0.56 = 0.62
        # Kappa = (0.7 - 0.62) / (1 - 0.62) = 0.08/0.38 ≈ 0.2105
        assert m.cohens_kappa == pytest.approx(0.08 / 0.38, abs=1e-4)

    def test_empty_lists(self):
        m = compute_metrics([], [])
        assert m.total_audited == 0
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1_score == 0.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="Length mismatch"):
            compute_metrics(["YES"], ["YES", "NO"])

    def test_zero_precision_division_safe(self):
        ai = ["NO", "NO"]
        hu = ["YES", "YES"]
        m = compute_metrics(ai, hu)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1_score == 0.0

    def test_zero_tp_and_fp(self):
        ai = ["NO", "NO"]
        hu = ["NO", "NO"]
        m = compute_metrics(ai, hu)
        assert m.precision == 0.0
        # recall = 0/0 = 0.0 (no positive cases to find)
        assert m.recall == 0.0
        assert m.f1_score == 0.0
        assert m.confusion_matrix.tn == 2

    def test_metrics_to_dict_structure(self):
        ai = ["YES", "NO"]
        hu = ["YES", "NO"]
        m = compute_metrics(ai, hu)
        d = metrics_to_dict(m)
        assert "total_audited" in d
        assert "confusion_matrix" in d
        assert "tp" in d["confusion_matrix"]
        assert "tn" in d["confusion_matrix"]
        assert "fp" in d["confusion_matrix"]
        assert "fn" in d["confusion_matrix"]
        assert "precision" in d
        assert "recall" in d
        assert "f1_score" in d
        assert "cohens_kappa" in d
        assert "interpretation" in d


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Audit Sample
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditSampleEndpoint:
    def test_sample_without_import_returns_400(self, test_env):
        resp = client.get("/api/audit/sample")
        assert resp.status_code == 400

    def test_sample_without_screening_returns_400(self, test_env):
        client.post(
            "/api/import",
            files={"file": ("test.csv", CSV_CONTENT, "text/csv")},
        )
        resp = client.get("/api/audit/sample")
        assert resp.status_code == 400

    def test_sample_returns_correct_structure(self, imported_env):
        resp = client.get("/api/audit/sample?size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_screened"] == CSV_ROWS
        assert data["sample_size"] <= CSV_ROWS
        assert len(data["items"]) == data["sample_size"]
        for item in data["items"]:
            assert "paper_id" in item
            assert "title" in item
            assert "abstract" in item
            assert "ai_decision" in item
            assert "ai_rationale" in item
            assert "applied_criteria_codes" in item
            assert "source_library" in item
            assert item["ai_decision"] in ("YES", "NO", "NEEDS_REVIEW")

    def test_sample_respects_size_param(self, imported_env):
        resp = client.get("/api/audit/sample?size=4")
        data = resp.json()
        assert data["sample_size"] >= 1

    def test_sample_all_strata_represented(self, imported_env):
        """With 3 INCLUDED, 5 EXCLUDED, 2 NEEDS_REVIEW each stratum should have at least 1."""
        resp = client.get("/api/audit/sample?size=10")
        data = resp.json()
        decisions_found = set(item["ai_decision"] for item in data["items"])
        assert "YES" in decisions_found
        assert "NO" in decisions_found
        assert "NEEDS_REVIEW" in decisions_found


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Audit Verdict
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditVerdictEndpoint:
    def test_post_verdict_success(self, imported_env):
        resp = client.post("/api/papers/T1/audit", json={"verdict": "YES"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"
        assert resp.json()["paper_id"] == "T1"

    def test_post_verdict_no(self, imported_env):
        resp = client.post("/api/papers/T2/audit", json={"verdict": "NO"})
        assert resp.status_code == 200

    def test_post_verdict_invalid_verdict_returns_422(self, imported_env):
        resp = client.post("/api/papers/T1/audit", json={"verdict": "MAYBE"})
        assert resp.status_code == 422

    def test_post_verdict_nonexistent_paper_returns_404(self, imported_env):
        resp = client.post("/api/papers/T999/audit", json={"verdict": "YES"})
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Audit Metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditMetricsEndpoint:
    def test_metrics_without_audits(self, imported_env):
        resp = client.get("/api/audit/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_audited"] == 0

    def test_metrics_correct_after_audits(self, imported_env):
        from src.api.routes import _get_decision_repo
        repo = _get_decision_repo()

        # Audit some papers with known outcomes
        # paper T1: AI=INCLUDED(YES), human says YES -> TP
        repo.save_audit("T1", "YES")
        # paper T2: AI=INCLUDED(YES), human says NO -> FP
        repo.save_audit("T2", "NO")
        # paper T3: AI=INCLUDED(YES), human says YES -> TP
        repo.save_audit("T3", "YES")
        # paper T4: AI=EXCLUDED(NO), human says NO -> TN
        repo.save_audit("T4", "NO")
        # paper T5: AI=EXCLUDED(NO), human says YES -> FN
        repo.save_audit("T5", "YES")

        resp = client.get("/api/audit/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_audited"] == 5
        assert data["confusion_matrix"] == {"tp": 2, "tn": 1, "fp": 1, "fn": 1}
        # Precision = 2/(2+1) = 2/3 ≈ 0.6667 (rounded to 4dp)
        assert data["precision"] == pytest.approx(2 / 3, abs=1e-4)
        # Recall = 2/(2+1) = 2/3 ≈ 0.6667
        assert data["recall"] == pytest.approx(2 / 3, abs=1e-4)
        # F1 = 2*(0.6667*0.6667)/(0.6667+0.6667) = 0.6667
        assert data["f1_score"] == pytest.approx(2 / 3, abs=1e-4)
        # Po = (2+1)/5 = 0.6
        # p_yes_ai = (2+1)/5 = 0.6
        # p_yes_human = (2+1)/5 = 0.6
        # p_no_ai = (1+1)/5 = 0.4
        # p_no_human = (1+1)/5 = 0.4
        # Pe = 0.6*0.6 + 0.4*0.4 = 0.36 + 0.16 = 0.52
        # Kappa = (0.6 - 0.52) / (1 - 0.52) = 0.08/0.48 ≈ 0.1667
        expected_kappa = (0.6 - 0.52) / (1 - 0.52)
        assert data["cohens_kappa"] == pytest.approx(expected_kappa, abs=1e-4)
        assert "Poor agreement" in data["interpretation"]

    def test_metrics_skips_needs_review(self, imported_env):
        """Papers where AI says NEEDS_REVIEW are excluded from metrics."""
        from src.api.routes import _get_decision_repo
        repo = _get_decision_repo()

        repo.save_audit("T9", "YES")
        repo.save_audit("T10", "YES")

        resp = client.get("/api/audit/metrics")
        data = resp.json()
        # total_audited includes all rows, but NEEDS_REVIEW is excluded from computation
        assert data["total_audited"] == 2
        assert data["confusion_matrix"]["tp"] == 0
        assert data["confusion_matrix"]["tn"] == 0
