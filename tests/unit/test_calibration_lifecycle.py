"""
Tests for calibration runtime lifecycle: service, snapshots, reset guards,
duplicate prevention, and frontend safety.
"""
import time
import threading
from unittest.mock import MagicMock, patch

from src.advisory.calibration_service import _CalibrationService
from src.advisory.calibration_runner import CalibrationRunner
from src.advisory.advisory_models import AdvisoryConfig
from src.advisory.advisory_orchestrator import (
    AdvisoryWorkerOrchestrator,
    reset_orchestrator_for_stage,
    lookup_orchestrator,
)
from src.advisory.advisory_queue import reset_queue_for_stage
from src.ui.theme import COLORS


# ---------------------------------------------------------------------------
# Part 1: Frontend-safe rendering
# ---------------------------------------------------------------------------

class TestFrontendSafety:
    def test_colors_has_bg_dark(self):
        assert "bg_dark" in COLORS

    def test_colors_safe_lookup(self):
        assert COLORS.get("bg_dark", "#000") is not None
        assert COLORS.get("nonexistent_key", "#fallback") == "#fallback"

    def test_all_ui_colors_have_fallbacks(self):
        used_keys = [
            "border", "bg_dark", "cyan", "success", "error", "warning",
            "text_muted", "bg_card", "bg_deep", "bg_surface", "bg_elevated",
            "border_light", "border_accent", "text_primary", "text_secondary",
            "cyan_dim", "cyan_bright", "cyan_subtle", "cyan_border",
            "info", "status_included", "status_excluded", "status_conflict",
            "status_consensus", "status_pending", "status_coded",
            "status_uncertain", "status_autonomous",
        ]
        for key in used_keys:
            assert key in COLORS, f"Missing COLORS key: {key}"


# ---------------------------------------------------------------------------
# Part 2: CalibrationService lifecycle
# ---------------------------------------------------------------------------

class TestCalibrationService:
    def test_get_or_create_runner(self):
        svc = _CalibrationService()
        runner = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert runner is not None
        assert runner.status == "idle"

    def test_get_or_create_runner_returns_same_instance(self):
        svc = _CalibrationService()
        r1 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        r2 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert r1 is r2

    def test_get_runner_nonexistent_session(self):
        svc = _CalibrationService()
        assert svc.get_runner("nonexistent") is None

    def test_get_runner_after_create(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert svc.get_runner("s1") is not None

    def test_stop_runner_nonexistent(self):
        svc = _CalibrationService()
        assert svc.stop_runner("nonexistent") is False

    def test_remove_runner(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert svc.remove_runner("s1") is True
        assert svc.get_runner("s1") is None

    def test_is_active_no_runner(self):
        svc = _CalibrationService()
        assert svc.is_active("nonexistent") is False

    def test_has_completed_no_runner(self):
        svc = _CalibrationService()
        assert svc.has_completed("nonexistent") is False

    def test_clear_completed(self):
        svc = _CalibrationService()
        r1 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        r2 = svc.get_or_create_runner("s2", [], protocol_version="2.0")
        r1._status = "completed"
        r2._status = "error"
        assert svc.clear_completed() == 2
        assert svc.get_runner("s1") is None
        assert svc.get_runner("s2") is None

    def test_clear_completed_keeps_running(self):
        svc = _CalibrationService()
        r1 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        r2 = svc.get_or_create_runner("s2", [], protocol_version="2.0")
        r1._status = "running"
        r2._status = "completed"
        assert svc.clear_completed() == 1
        assert svc.get_runner("s1") is not None

    def test_list_active_runs(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        active = svc.list_active_runs()
        assert len(active) == 1
        assert active[0]["status"] == "idle"

    def test_runner_key_unique_by_protocol(self):
        svc = _CalibrationService()
        r1 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        r2 = svc.get_or_create_runner("s2", [], protocol_version="2.0")
        assert r1 is not r2

    def test_stop_all(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        svc.get_or_create_runner("s2", [], protocol_version="2.0")
        count = svc.stop_all()
        assert count == 2


# ---------------------------------------------------------------------------
# Part 3: Duplicate start prevention
# ---------------------------------------------------------------------------

class TestDuplicatePrevention:
    def test_run_async_idempotent(self):
        runner = CalibrationRunner([MagicMock()], config=AdvisoryConfig(),
                                    protocol_version="1.0")
        t1 = runner.run_async()
        t2 = runner.run_async()
        assert t1 is t2
        runner.stop()

    def test_run_async_returns_none_when_completed(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner._status = "completed"
        assert runner.run_async() is None

    def test_service_prevents_duplicate_runners(self):
        svc = _CalibrationService()
        r1 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        r2 = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert r1 is r2


# ---------------------------------------------------------------------------
# Part 4: Reset blocking during active runs
# ---------------------------------------------------------------------------

class TestResetGuards:
    def test_can_reset_stage_no_orchestrator(self):
        from src.advisory.advisory_orchestrator import _can_reset_stage
        assert _can_reset_stage("ic") is True

    def test_can_reset_stage_with_orchestrator_no_worker(self, monkeypatch):
        from src.advisory.advisory_orchestrator import (_can_reset_stage,
                                                        _global_orchestrator_ic)
        orch = AdvisoryWorkerOrchestrator(stage="ic")
        monkeypatch.setattr("src.advisory.advisory_orchestrator._global_orchestrator_ic", orch)
        assert _can_reset_stage("ic") is True

    def test_can_reset_queue_no_orchestrator(self):
        from src.advisory.advisory_queue import _can_reset_queue
        assert _can_reset_queue("ic") is True

    def test_reset_orchestrator_raises_with_active_worker(self, monkeypatch):
        from src.advisory.advisory_orchestrator import (_can_reset_stage,
                                                        _global_orchestrator_ic)
        orch = AdvisoryWorkerOrchestrator(stage="ic")
        orch._worker_thread = MagicMock()
        orch._worker_thread.is_alive.return_value = True
        monkeypatch.setattr("src.advisory.advisory_orchestrator._global_orchestrator_ic", orch)
        import pytest
        with pytest.raises(RuntimeError, match="worker is still active"):
            reset_orchestrator_for_stage("ic", force=False)

    def test_reset_orchestrator_force_bypasses_guard(self, monkeypatch):
        from src.advisory.advisory_orchestrator import (_can_reset_stage,
                                                        _global_orchestrator_ic)
        orch = AdvisoryWorkerOrchestrator(stage="ic")
        orch._worker_thread = MagicMock()
        orch._worker_thread.is_alive.return_value = True
        monkeypatch.setattr("src.advisory.advisory_orchestrator._global_orchestrator_ic", orch)
        reset_orchestrator_for_stage("ic", force=True)
        assert _global_orchestrator_ic is None

    def test_reset_queue_raises_with_active_worker(self, monkeypatch):
        from src.advisory.advisory_orchestrator import (_can_reset_stage,
                                                        _global_orchestrator_ic)
        orch = AdvisoryWorkerOrchestrator(stage="ic")
        orch._worker_thread = MagicMock()
        orch._worker_thread.is_alive.return_value = True
        monkeypatch.setattr("src.advisory.advisory_orchestrator._global_orchestrator_ic", orch)
        import pytest
        with pytest.raises(RuntimeError, match="worker is still active"):
            reset_queue_for_stage("ic", force=False)

    def test_reset_orchestrator_idle_succeeds(self, monkeypatch):
        from src.advisory.advisory_orchestrator import _global_orchestrator_ic
        orch = AdvisoryWorkerOrchestrator(stage="ic")
        monkeypatch.setattr("src.advisory.advisory_orchestrator._global_orchestrator_ic", orch)
        reset_orchestrator_for_stage("ic", force=False)
        assert _global_orchestrator_ic is None


# ---------------------------------------------------------------------------
# Part 5: Runtime snapshot consistency
# ---------------------------------------------------------------------------

class TestRuntimeSnapshots:
    def test_snapshot_includes_status(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        snap = runner.calibration_progress
        assert "status" in snap

    def test_snapshot_includes_stage(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        snap = runner.calibration_progress
        assert "current_stage" in snap

    def test_snapshot_includes_sample_size(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(calibration_sample_size=5),
                                    protocol_version="1.0")
        snap = runner.calibration_progress
        assert snap["sample_size"] == 5

    def test_snapshot_reflects_current_status(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        assert runner.calibration_progress["status"] == "idle"
        runner._status = "stopped"
        assert runner.calibration_progress["status"] == "stopped"

    def test_snapshot_reflects_running_status(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner._status = "running"
        assert runner.calibration_progress["status"] == "running"

    def test_snapshot_not_touch_live_queue(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        snap = runner.calibration_progress
        assert "ec_total" in snap
        assert "ec_completed" in snap
        assert "timestamp" in snap


# ---------------------------------------------------------------------------
# Part 6: Worker stop/join correctness
# ---------------------------------------------------------------------------

class TestWorkerStop:
    def test_stop_idle_runner(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner.stop()
        assert runner._stop_event.is_set()

    def test_stop_event_prevents_run_stage(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner._stop_event.set()
        result = runner._run_stage("ec", [MagicMock()])
        assert result is False

    def test_duplicate_stop_safe(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner.stop()
        runner.stop()
        assert runner._stop_event.is_set()

    def test_stop_after_completed(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        runner._status = "completed"
        runner.stop()
        assert runner._stop_event.is_set()


# ---------------------------------------------------------------------------
# Part 7: CalibrationRunner lifecycle
# ---------------------------------------------------------------------------

class TestCalibrationRunnerLifecycle:
    def test_initial_status_is_idle(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        assert runner.status == "idle"
        assert runner.current_stage is None
        assert runner.report is None

    def test_run_async_creates_thread(self):
        articles = [MagicMock() for _ in range(3)]
        runner = CalibrationRunner(articles, config=AdvisoryConfig(),
                                    protocol_version="1.0")
        with patch.object(runner, '_run_stage', return_value=True):
            with patch.object(runner, '_wait_for_completion', return_value=True):
                thread = runner.run_async()
                assert thread is not None
                assert thread.is_alive()
                runner.stop()

    def test_run_async_sets_running_status(self):
        articles = [MagicMock() for _ in range(3)]
        runner = CalibrationRunner(articles, config=AdvisoryConfig(),
                                    protocol_version="1.0")
        with patch.object(runner, '_run_stage', return_value=True):
            with patch.object(runner, '_wait_for_completion', return_value=True):
                runner.run_async()
                assert runner.status == "running"
                runner.stop()

    def test_run_async_idempotent_after_instant_error(self):
        articles = [MagicMock() for _ in range(3)]
        runner = CalibrationRunner(articles, config=AdvisoryConfig(),
                                    protocol_version="1.0")
        with patch.object(runner, '_run_stage', return_value=True):
            with patch.object(runner, '_wait_for_completion', return_value=True):
                t1 = runner.run_async()
                t2 = runner.run_async()
                assert t1 is t2
                runner.stop()

    def test_report_none_before_completion(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        assert runner.report is None

    def test_artifact_path_none_before_completion(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        assert runner.artifact_path is None

    def test_empty_articles_returns_error(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        result = runner.run()
        assert result.get("status") == "error"
        assert "No articles" in result.get("error", "")

    def test_run_async_empty_articles_fast_error(self):
        runner = CalibrationRunner([], config=AdvisoryConfig(), protocol_version="1.0")
        thread = runner.run_async()
        thread.join(timeout=5)
        assert runner.status == "error"


# ---------------------------------------------------------------------------
# Part 8: Service + Runner integration
# ---------------------------------------------------------------------------

class TestServiceRunnerIntegration:
    def test_service_run_async_idempotent(self):
        svc = _CalibrationService()
        articles = [MagicMock() for _ in range(3)]
        runner = svc.get_or_create_runner("s1", articles, protocol_version="1.0")
        with patch.object(runner, '_run_stage', return_value=True):
            with patch.object(runner, '_wait_for_completion', return_value=True):
                t1 = runner.run_async()
                t2 = runner.run_async()
                assert t1 is t2
                runner.stop()

    def test_service_remove_stops_nothing(self):
        svc = _CalibrationService()
        runner = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        svc.remove_runner("s1")
        assert svc.get_runner("s1") is None

    def test_service_is_active_false_when_idle(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        assert svc.is_active("s1") is False

    def test_service_is_active_true_when_running(self):
        svc = _CalibrationService()
        runner = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        runner._status = "running"
        assert svc.is_active("s1") is True

    def test_service_get_runner_by_key(self):
        svc = _CalibrationService()
        runner = svc.get_or_create_runner("s1", [], protocol_version="1.0")
        from src.advisory.calibration_artifact import _compute_protocol_hash
        key = _compute_protocol_hash("1.0")
        assert svc.get_runner_by_key(key) is runner

    def test_service_len(self):
        svc = _CalibrationService()
        svc.get_or_create_runner("s1", [], protocol_version="1.0")
        svc.get_or_create_runner("s2", [], protocol_version="2.0")
        assert len(svc) == 2
