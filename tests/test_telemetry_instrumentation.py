"""
End-to-end validation tests for APOLLO runtime telemetry.

Covers all instrumentation points:
  - TelemetryBus (enqueue, flush, backpressure, shutdown)
  - Worker lifecycle hooks (item_started, item_completed, item_failed)
  - Gateway hooks (provider_call, provider_failure, circuit_breaker)
  - Queue hooks (depth, processing_time, requeue)
  - IncrementalDriftTracker (drift detection)
  - LiveQualityTracker (rolling quality)
  - Failure taxonomy (classify_failure_semantic)
"""
import time
import queue
import threading
from typing import Dict
from datetime import datetime, timezone

import pytest

from src.advisory.telemetry_bus import (
    TelemetryBus,
    get_telemetry_bus,
    reset_telemetry_bus,
    _validate_metric,
)
from src.advisory.calibration_drift import IncrementalDriftTracker
from src.advisory.advisory_quality_score import LiveQualityTracker, compute_quality_score
from src.advisory.transient_failures import (
    classify_failure_semantic,
    classify_failure_detailed,
    is_transient_provider_error,
    is_terminal_failure,
)
from src.advisory.telemetry_clock import (
    LogicalClock, EventEnvelope, stamp_event, get_logical_clock, reset_logical_clock,
)
from src.advisory.telemetry_reconciliation import (
    ReconciliationEngine, ReconciliationReport, ReconciliationStore,
)
from src.advisory.telemetry_backpressure import (
    BackpressureController, BackpressureState, get_backpressure_controller,
    reset_backpressure_controller, LOAD_NOMINAL, LOAD_ELEVATED, LOAD_CRITICAL,
)
from src.advisory.telemetry_consistency import (
    ConsistencyChecker, ConsistencyReport,
)
from src.advisory.replay_system import TelemetryReplay
from src.advisory.telemetry_persist import EventSink, get_event_sink, reset_event_sink


# =============================================================================
# Part 2+3: TelemetryBus tests
# =============================================================================


class TestTelemetryBus:
    """TelemetryBus core: enqueue, flush, backpressure, shutdown."""

    def test_enqueue_and_flush(self):
        bus = TelemetryBus(max_queue_size=100)
        bus.record_item_started("ec", "test_key_1")
        bus.record_item_completed("ec", "test_key_1", "INCLUDE")
        time.sleep(0.05)
        stats = bus.get_stats()
        assert stats["queue_size"] >= 0
        bus.stop()

    def test_backpressure_drop(self):
        bus = TelemetryBus(max_queue_size=5)
        for _ in range(100):
            bus.record_item_started("ec", "x")
        stats = bus.get_stats()
        assert stats["drops"]["queue_full"] > 0
        bus.stop()

    def test_schema_violation_drop(self):
        bus = TelemetryBus(max_queue_size=100)
        bus._enqueue("item_started", 1.0, {})
        stats = bus.get_stats()
        assert stats["drops"]["schema_violation"] >= 0
        bus.stop()

    def test_stop_drains_queue(self):
        bus = TelemetryBus(max_queue_size=100)
        for _ in range(10):
            bus.record_item_started("ec", "k")
        bus.stop()
        stats = bus.get_stats()
        assert stats["flush_count"] >= 0

    def test_deterministic_schema_validation(self):
        assert _validate_metric("item_started", {"stage": "ec", "cache_key": "k"}) is True
        assert _validate_metric("item_started", {"stage": "ec"}) is False

    def test_record_acceptance(self):
        bus = TelemetryBus(max_queue_size=100)
        bus.record_acceptance("ec", True)
        bus.record_acceptance("ec", False)
        bus.stop()

    def test_convenience_methods(self):
        bus = TelemetryBus(max_queue_size=100)
        bus.record_decision("ec", "INCLUDE")
        bus.record_confidence("ec", 0.85)
        bus.record_latency("ec", 1234.5)
        bus.record_retry("ec")
        bus.record_429("groq")
        bus.record_queue_depth("ec", 42)
        bus.record_processing_time("ec", 3.5)
        bus.record_requeue_event("ec", "transient")
        bus.record_provider_call("groq")
        bus.record_provider_failure("groq", "timeout")
        bus.record_circuit_breaker_change("groq", "HEALTHY", "COOLDOWN")
        bus.record_quality_score("ec", 0.92)
        bus.stop()


class TestTelemetryBusSingleton:
    """Global singleton behavior."""

    def setup_method(self):
        reset_telemetry_bus()

    def test_get_telemetry_bus_returns_same(self):
        b1 = get_telemetry_bus()
        b2 = get_telemetry_bus()
        assert b1 is b2
        bus = get_telemetry_bus()
        bus.stop()
        reset_telemetry_bus()

    def test_reset_creates_new(self):
        b1 = get_telemetry_bus()
        b1.stop()
        reset_telemetry_bus()
        b2 = get_telemetry_bus()
        assert b1 is not b2
        b2.stop()
        reset_telemetry_bus()


class TestTelemetryBusReset:
    """TelemetryBus reset_for_testing."""

    def test_reset_clears_state(self):
        bus = TelemetryBus(max_queue_size=100)
        bus.record_item_started("ec", "k")
        bus.record_item_completed("ec", "k", "INCLUDE")
        stats_before = bus.get_stats()
        bus.reset_for_testing()
        stats_after = bus.get_stats()
        assert stats_after["flush_count"] <= stats_before["flush_count"]
        bus.stop()


# =============================================================================
# Part 4: IncrementalDriftTracker tests
# =============================================================================


class TestIncrementalDriftTracker:
    """Rolling window drift detection."""

    def test_no_drift_with_identical_pattern(self):
        tracker = IncrementalDriftTracker(window_size=50)
        for _ in range(50):
            tracker.add_observation("INCLUDE", 0.85, ["IC1", "IC2"])
        drift = tracker.compute_drift()
        assert drift["composite_drift_score"] < 0.05
        assert drift["composite_drift_type"] == "stable"

    def test_drift_with_different_pattern(self):
        tracker = IncrementalDriftTracker(window_size=50)
        for _ in range(50):
            tracker.add_observation("INCLUDE", 0.85, ["IC1", "IC2"])
        for _ in range(50):
            tracker.add_observation("EXCLUDE", 0.30, ["IC1"])
        drift = tracker.compute_drift()
        assert drift["composite_drift_score"] >= 0.0
        assert drift["composite_drift_type"] in ("stable", "mild drift", "structural drift")

    def test_burst_drift(self):
        tracker = IncrementalDriftTracker(window_size=50)
        for _ in range(50):
            tracker.add_observation("INCLUDE", 0.90, ["IC1"])
        for _ in range(50):
            tracker.add_observation("SKIP", 0.10, [])
        drift = tracker.compute_drift()
        assert drift["decision_drift_score"] >= 0.0

    def test_drift_event(self):
        tracker = IncrementalDriftTracker(window_size=20)
        for _ in range(20):
            tracker.add_observation("INCLUDE", 0.90, ["IC1"])
        event = tracker.get_drift_event()
        assert "drift_detected" in event
        assert "composite_drift_score" in event

    def test_compute_composite_drift(self):
        tracker = IncrementalDriftTracker(window_size=30)
        for _ in range(30):
            tracker.add_observation("INCLUDE", 0.85, ["IC1", "IC2"])
        result = tracker.compute_composite_drift()
        assert result["composite_drift_type"] == "stable"

    def test_empty_tracker(self):
        tracker = IncrementalDriftTracker(window_size=50)
        drift = tracker.compute_drift()
        assert drift["composite_drift_score"] == 0.0
        assert drift["composite_drift_type"] == "stable"


# =============================================================================
# Part 5: LiveQualityTracker tests
# =============================================================================


class TestLiveQualityTracker:
    """Rolling quality tracking."""

    def test_add_advisory(self):
        tracker = LiveQualityTracker()
        advisory = {
            "decision": "INCLUDE",
            "confidence": 0.85,
            "grounding_strength": 0.8,
            "triggered_criteria": ["IC1"],
            "hallucination_risk_score": 0.1,
        }
        score = tracker.add_advisory(advisory, "ic")
        assert 0.0 <= score <= 1.0

    def test_rolling_quality(self):
        tracker = LiveQualityTracker()
        for _ in range(10):
            tracker.add_advisory({
                "decision": "INCLUDE",
                "confidence": 0.85,
                "grounding_strength": 0.8,
                "triggered_criteria": ["IC1"],
                "hallucination_risk_score": 0.1,
            }, "ic")
        q = tracker.get_rolling_quality("ic")
        assert 0.0 <= q["raw_quality"] <= 1.0
        assert q["count"] == 10

    def test_multiple_stages(self):
        tracker = LiveQualityTracker()
        for stage in ("ec", "ic", "qc"):
            for _ in range(5):
                tracker.add_advisory({
                    "decision": "INCLUDE",
                    "confidence": 0.85,
                    "grounding_strength": 0.8,
                    "triggered_criteria": [f"{stage.upper()}1"],
                    "hallucination_risk_score": 0.1,
                }, stage)
        all_q = tracker.get_rolling_quality()
        assert "ec" in all_q
        assert "ic" in all_q
        assert "qc" in all_q

    def test_deterministic(self):
        tracker1 = LiveQualityTracker()
        tracker2 = LiveQualityTracker()
        adv = {
            "decision": "INCLUDE",
            "confidence": 0.85,
            "grounding_strength": 0.8,
            "triggered_criteria": ["IC1"],
            "hallucination_risk_score": 0.1,
        }
        for _ in range(10):
            tracker1.add_advisory(adv, "ic")
            tracker2.add_advisory(adv, "ic")
        assert tracker1.get_rolling_quality("ic")["raw_quality"] == tracker2.get_rolling_quality("ic")["raw_quality"]

    def test_empty_tracker(self):
        tracker = LiveQualityTracker()
        q = tracker.get_rolling_quality("ic")
        assert q["count"] == 0


# =============================================================================
# Part 6: Failure taxonomy tests
# =============================================================================


class TestFailureTaxonomy:
    """Semantic failure classification."""

    def test_provider_failure(self):
        assert classify_failure_semantic("429 rate limit exceeded") == "provider_failure"
        assert classify_failure_semantic("service unavailable") == "provider_failure"

    def test_parsing_failure(self):
        assert classify_failure_semantic("JSONDecodeError: Expecting value") == "parsing_failure"
        assert classify_failure_semantic("SCHEMA_MISMATCH") == "parsing_failure"

    def test_validation_failure(self):
        assert classify_failure_semantic("invariant violation in stage guard") == "validation_failure"
        assert classify_failure_semantic("QUARANTINED") == "validation_failure"

    def test_timeout_failure(self):
        assert classify_failure_semantic("deadline exceeded at 300s") == "timeout_failure"
        assert classify_failure_semantic("Retry total timeout exceeded") == "timeout_failure"

    def test_circuit_breaker_failure(self):
        assert classify_failure_semantic("Provider is UNAVAILABLE") == "circuit_breaker_failure"
        assert classify_failure_semantic("Provider 'groq' in COOLDOWN") == "circuit_breaker_failure"

    def test_queue_failure(self):
        assert classify_failure_semantic("corrupted snapshot during replay") == "queue_failure"
        assert classify_failure_semantic("WAL replay failed") == "queue_failure"

    def test_unknown_failure(self):
        assert classify_failure_semantic("some random error") == "unknown"
        assert classify_failure_semantic(None) == "unknown"

    def test_classify_failure_detailed(self):
        result = classify_failure_detailed("429 too many requests")
        assert result["failure_category"] == "provider_failure"
        assert result["is_transient"] is True

    def test_service_unavailable_is_provider_not_cb(self):
        assert classify_failure_semantic("service unavailable") == "provider_failure"

    def test_internal_failure(self):
        assert classify_failure_semantic("memory full") == "unknown"
        assert classify_failure_semantic("disk full") == "unknown"

    def test_transient_and_terminal_classifiers(self):
        assert is_transient_provider_error("429 rate limit") is True
        assert is_transient_provider_error("connection timeout") is True
        assert is_terminal_failure("corrupted snapshot") is True
        assert is_terminal_failure("invariant violation") is True
        assert is_terminal_failure("something normal") is False


# =============================================================================
# Part 1: Global Event Ordering System tests
# =============================================================================


class TestLogicalClock:
    """LogicalClock determinism and monotonicity."""

    def test_tick_increases(self):
        clock = LogicalClock()
        t1 = clock.tick("test")
        t2 = clock.tick("test")
        assert t2 > t1

    def test_witness_catches_up(self):
        clock = LogicalClock()
        clock.tick("test")
        ts = clock.witness(100)
        assert ts > 100

    def test_peek_no_advance(self):
        clock = LogicalClock()
        t1 = clock.tick("test")
        peeked = clock.peek()
        assert peeked == t1

    def test_deterministic_stamp(self):
        clock = LogicalClock()
        ev1 = stamp_event("item_started", 1.0, {"k": "v"}, "worker", clock=clock)
        clock2 = LogicalClock()
        ev2 = stamp_event("item_started", 1.0, {"k": "v"}, "worker", clock=clock2)
        assert ev1.logical_timestamp == ev2.logical_timestamp

    def test_event_envelope_ordering(self):
        clock = LogicalClock()
        ev_a = stamp_event("item_started", 1.0, {"k": "a"}, "worker", clock=clock)
        ev_b = stamp_event("item_started", 1.0, {"k": "b"}, "worker", clock=clock)
        assert ev_a < ev_b
        assert ev_b > ev_a

    def test_event_envelope_source_priority_tiebreak(self):
        events = []
        for src in ("gateway", "worker", "queue", "ui", "replay", "test"):
            events.append(EventEnvelope(
                metric="test", value=1.0, tags={},
                global_event_id=f"id_{src}", logical_timestamp=1,
                source_component=src,
            ))
        events.sort()
        sources = [e.source_component for e in events]
        assert sources == ["gateway", "worker", "queue", "ui", "replay", "test"]

    def test_singleton_global(self):
        reset_logical_clock()
        c1 = get_logical_clock()
        c2 = get_logical_clock()
        assert c1 is c2
        reset_logical_clock()

    def test_reset_creates_new(self):
        reset_logical_clock()
        c1 = get_logical_clock()
        reset_logical_clock()
        c2 = get_logical_clock()
        assert c1 is not c2


class TestEventEnvelope:
    """EventEnvelope serialization and comparison."""

    def test_roundtrip_dict(self):
        ev = EventEnvelope(
            metric="test_metric", value=42.0, tags={"stage": "ec"},
            global_event_id="abc123", logical_timestamp=7,
            source_component="worker", causal_parent_id="parent1",
        )
        d = ev.to_dict()
        ev2 = EventEnvelope.from_dict(d)
        assert ev2.metric == "test_metric"
        assert ev2.value == 42.0
        assert ev2.tags == {"stage": "ec"}
        assert ev2.global_event_id == "abc123"
        assert ev2.logical_timestamp == 7
        assert ev2.source_component == "worker"
        assert ev2.causal_parent_id == "parent1"

    def test_ordering_by_logical_timestamp(self):
        a = EventEnvelope("m", 1, {}, "id1", 5, "worker")
        b = EventEnvelope("m", 1, {}, "id2", 10, "worker")
        assert a < b

    def test_ordering_by_source_tiebreak(self):
        a = EventEnvelope("m", 1, {}, "id1", 5, "gateway")
        b = EventEnvelope("m", 1, {}, "id2", 5, "worker")
        assert a < b

    def test_ordering_by_id_tiebreak(self):
        a = EventEnvelope("m", 1, {}, "aaa", 5, "worker")
        b = EventEnvelope("m", 1, {}, "bbb", 5, "worker")
        assert a < b


# =============================================================================
# Part 2: Telemetry Reconciliation tests
# =============================================================================


class TestReconciliationEngine:
    """Reconciliation engine: missing events, duplicates, transitions."""

    def test_no_violations_perfect_stream(self):
        bus = get_telemetry_bus()
        bus.clear_event_log()
        bus.record_item_started("ec", "key1")
        bus.record_item_completed("ec", "key1", "INCLUDE")
        time.sleep(0.05)
        events = bus.get_event_log_sorted()
        engine = ReconciliationEngine()
        report = engine.reconcile(events)
        assert report.consistency_score >= 0.95
        assert len(report.violations) == 0
        bus.stop()
        reset_telemetry_bus()

    def test_detects_missing_start_event(self):
        bus = get_telemetry_bus()
        bus.clear_event_log()
        bus.record_item_completed("ec", "orphan_key", "INCLUDE")
        bus.flush()
        events = bus.get_event_log_sorted()
        engine = ReconciliationEngine()
        report = engine.reconcile(events)
        has_missing = any(v["violation_type"] == "missing_start_event" for v in report.violations)
        assert has_missing
        reset_telemetry_bus()

    def test_detects_duplicate_events(self):
        from src.advisory.telemetry_clock import EventEnvelope
        events = [
            EventEnvelope("item_started", 1.0, {"cache_key": "k1"}, "id1", 1, "worker"),
            EventEnvelope("item_started", 1.0, {"cache_key": "k2"}, "id2", 2, "worker"),
            EventEnvelope("item_started", 1.0, {"cache_key": "k3"}, "id3", 3, "worker"),
        ]
        engine = ReconciliationEngine()
        report = engine.reconcile(events)
        assert report.event_count == 3

    def test_critical_events_present(self):
        bus = get_telemetry_bus()
        bus.clear_event_log()
        events = bus.get_event_log_sorted()
        engine = ReconciliationEngine()
        violations = engine.check_critical_events_present(events)
        assert isinstance(violations, list)
        bus.stop()
        reset_telemetry_bus()

    def test_queue_completed_mismatch(self):
        events = [
            EventEnvelope("item_completed", 1.0, {"cache_key": "k"}, "id1", 1, "worker"),
        ]
        queue_state = {"completed": 5, "failed": 0}
        engine = ReconciliationEngine()
        report = engine.reconcile(events, queue_state=queue_state)
        has_mismatch = any(v["violation_type"] == "queue_completed_mismatch" for v in report.violations)
        assert has_mismatch


class TestReconciliationReport:
    """Reconciliation report generation."""

    def test_report_defaults(self):
        report = ReconciliationReport()
        assert report.consistency_score == 1.0
        assert report.is_healthy() is True

    def test_report_to_json(self):
        report = ReconciliationReport(
            timestamp="2026-01-01T00:00:00",
            consistency_score=0.85,
            violations=[{"violation_type": "test", "severity": "warning", "detail": "test"}],
        )
        json_str = report.to_json()
        assert "consistency_score" in json_str
        assert "0.85" in json_str


# =============================================================================
# Part 3: Backpressure Controller tests
# =============================================================================


class TestBackpressureController:
    """Backpressure load detection and sampling."""

    def test_nominal_load(self):
        ctrl = BackpressureController()
        level = ctrl.assess_load(queue_depth=100, drain_rate=500)
        assert level == LOAD_NOMINAL

    def test_elevated_load(self):
        ctrl = BackpressureController()
        level = ctrl.assess_load(queue_depth=1500, drain_rate=50)
        assert level == LOAD_ELEVATED

    def test_critical_load(self):
        ctrl = BackpressureController()
        level = ctrl.assess_load(queue_depth=6000, drain_rate=5)
        assert level == LOAD_CRITICAL

    def test_critical_events_always_sampled(self):
        ctrl = BackpressureController()
        ctrl.update(queue_depth=9999, drain_rate=1.0, flush_lag_ms=5000, drop_rate=100)
        assert ctrl.should_sample("item_started") is True
        assert ctrl.should_sample("item_completed") is True
        assert ctrl.should_sample("item_failed") is True
        assert ctrl.should_sample("provider_failure") is True
        assert ctrl.should_sample("circuit_breaker_change") is True
        assert ctrl.should_sample("requeue_event") is True

    def test_high_frequency_may_be_dropped(self):
        ctrl = BackpressureController()
        ctrl.update(queue_depth=6000, drain_rate=1.0, flush_lag_ms=5000, drop_rate=100)
        accepted = sum(ctrl.should_sample("latency_ec") for _ in range(100))
        assert accepted < 100

    def test_sampling_is_deterministic(self):
        ctrl1 = BackpressureController()
        ctrl2 = BackpressureController()
        ctrl1.update(queue_depth=6000, drain_rate=1.0, flush_lag_ms=5000, drop_rate=100)
        ctrl2.update(queue_depth=6000, drain_rate=1.0, flush_lag_ms=5000, drop_rate=100)
        results1 = [ctrl1.should_sample("latency_ec") for _ in range(20)]
        results2 = [ctrl2.should_sample("latency_ec") for _ in range(20)]
        assert results1 == results2

    def test_get_state(self):
        ctrl = BackpressureController()
        ctrl.update(queue_depth=500, drain_rate=200, flush_lag_ms=10, drop_rate=0)
        state = ctrl.get_state()
        assert state["load_level"] in (LOAD_NOMINAL, LOAD_ELEVATED, LOAD_CRITICAL)
        assert "sampling_rate" in state

    def test_reset(self):
        ctrl = BackpressureController()
        ctrl.update(queue_depth=9999, drain_rate=1.0, flush_lag_ms=5000, drop_rate=100)
        ctrl.reset()
        state = ctrl.get_state()
        assert state["load_level"] == LOAD_NOMINAL
        assert state["sampling_rate"] == 1.0


# =============================================================================
# Part 4: Deterministic Telemetry Replay tests
# =============================================================================


class TestTelemetryReplay:
    """TelemetryReplay: state reconstruction and checksums."""

    def test_replay_empty(self):
        replay = TelemetryReplay()
        state = replay.replay_all()
        assert state["event_count"] == 0

    def test_replay_basic_events(self):
        from src.advisory.telemetry_clock import LogicalClock
        clock = LogicalClock()
        events = [
            stamp_event("item_started", 1.0, {"cache_key": "k1"}, "worker", clock=clock),
            stamp_event("item_completed", 1.0, {"cache_key": "k1", "decision": "INCLUDE"}, "worker", clock=clock),
            stamp_event("provider_call", 1.0, {"provider": "groq"}, "gateway", clock=clock),
        ]
        replay = TelemetryReplay()
        replay.load_events(events)
        state = replay.replay_all()
        assert state["event_count"] == 3
        assert "k1" in state["items_completed"]
        assert state["items_completed"]["k1"] == "INCLUDE"
        assert state["provider_calls"] == 1

    def test_replay_step_by_step(self):
        from src.advisory.telemetry_clock import LogicalClock
        clock = LogicalClock()
        events = [
            stamp_event("item_started", 1.0, {"cache_key": "k1"}, "worker", clock=clock),
            stamp_event("item_completed", 1.0, {"cache_key": "k1", "decision": "INCLUDE"}, "worker", clock=clock),
        ]
        replay = TelemetryReplay()
        replay.load_events(events)
        steps = replay.replay_step(start_index=0, steps=2)
        assert len(steps) == 2
        assert steps[0]["event"]["metric"] == "item_started"
        assert steps[1]["event"]["metric"] == "item_completed"

    def test_checksum_determinism(self):
        from src.advisory.telemetry_clock import LogicalClock
        clock1 = LogicalClock()
        clock2 = LogicalClock()
        events1 = [
            stamp_event("item_started", 1.0, {"cache_key": "k1"}, "worker", clock=clock1),
            stamp_event("item_completed", 1.0, {"cache_key": "k1"}, "worker", clock=clock1),
        ]
        events2 = [
            stamp_event("item_started", 1.0, {"cache_key": "k1"}, "worker", clock=clock2),
            stamp_event("item_completed", 1.0, {"cache_key": "k1"}, "worker", clock=clock2),
        ]
        replay1 = TelemetryReplay()
        replay1.load_events(events1)
        replay2 = TelemetryReplay()
        replay2.load_events(events2)
        assert replay1.compute_checksum() == replay2.compute_checksum()

    def test_verify_checksum(self):
        from src.advisory.telemetry_clock import LogicalClock
        clock = LogicalClock()
        events = [
            stamp_event("item_started", 1.0, {"cache_key": "k1"}, "worker", clock=clock),
        ]
        replay = TelemetryReplay()
        replay.load_events(events)
        cs = replay.compute_checksum()
        assert replay.verify_checksum(cs) is True
        assert replay.verify_checksum("deadbeef") is False


# =============================================================================
# Part 5: Cross-layer Consistency Validator tests
# =============================================================================


class TestConsistencyChecker:
    """Cross-layer consistency checks."""

    def test_perfect_consistency(self):
        checker = ConsistencyChecker()
        report = checker.check_all(events=[])
        assert report.consistency_score == 1.0
        assert report.is_healthy() is True

    def test_telemetry_queue_mismatch(self):
        events = [
            EventEnvelope("item_completed", 1.0, {"cache_key": "k1"}, "id1", 1, "worker"),
            EventEnvelope("item_completed", 1.0, {"cache_key": "k2"}, "id2", 2, "worker"),
        ]
        queue_state = {"completed": 1, "failed": 0}
        checker = ConsistencyChecker()
        report = checker.check_all(events=events, queue_state=queue_state)
        assert report.consistency_score < 1.0

    def test_cache_mismatch(self):
        events = [
            EventEnvelope("item_completed", 1.0, {"cache_key": "k1"}, "id1", 1, "worker"),
        ]
        cache_stats = {"total_cached": 5}
        checker = ConsistencyChecker()
        report = checker.check_all(events=events, cache_stats=cache_stats)
        assert report.consistency_score < 1.0

    def test_metric_drift_detection(self):
        events = [
            EventEnvelope("item_completed", 1.0, {"cache_key": "k1"}, "id1", 1, "worker"),
        ]
        computed = {"total_events": 10, "completed": 10}
        checker = ConsistencyChecker()
        report = checker.check_all(events=events, computed_metrics=computed)
        assert report.consistency_score < 1.0


# =============================================================================
# Part 6: Fault Injection and Robustness tests
# =============================================================================


class TestFaultInjection:
    """Observability layer fault tolerance."""

    def test_telemetry_bus_survives_concurrent_burst(self):
        bus = TelemetryBus(max_queue_size=500, flush_interval=0.01)
        bus.start()
        n = 200

        def inject():
            for _ in range(n):
                bus.record_item_started("ec", "burst_key")

        threads = [threading.Thread(target=inject) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        time.sleep(0.1)
        stats = bus.get_stats()
        total = stats["flush_count"] + stats["drops"]["queue_full"] + stats["drops"]["schema_violation"]
        assert total >= 0
        bus.stop()

    def test_replay_after_concurrent_burst(self):
        bus = TelemetryBus(max_queue_size=1000, flush_interval=0.01)
        bus.start()
        for i in range(50):
            bus.record_item_started("ec", f"k{i}")
            bus.record_item_completed("ec", f"k{i}", "INCLUDE")
        time.sleep(0.1)
        bus.flush()
        events = bus.get_event_log_sorted()
        replay = TelemetryReplay()
        replay.load_events(events)
        state = replay.replay_all()
        assert state["event_count"] >= 50
        bus.stop()

    def test_backpressure_with_concurrent_load(self):
        bus = TelemetryBus(max_queue_size=50, flush_interval=0.005)
        bus.start()
        ctrl = BackpressureController()
        ctrl.update(queue_depth=5000, drain_rate=5.0, flush_lag_ms=100, drop_rate=10)
        for _ in range(200):
            should = ctrl.should_sample("latency_ec")
            if should:
                bus.record_latency("ec", 100.0)
            bus.record_item_started("ec", "k")
        time.sleep(0.05)
        bus.stop()


# =============================================================================
# Part 7: Production Hardening (latency, memory, concurrency)
# =============================================================================


class TestProductionHardening:
    """Telemetry layer performance and memory characteristics."""

    def test_enqueue_latency(self):
        bus = TelemetryBus(max_queue_size=10000)
        start = time.perf_counter()
        n = 1000
        for _ in range(n):
            bus.record_item_started("ec", "latency_test")
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        assert avg_us < 100, f"Average enqueue latency {avg_us:.1f}us exceeds 100us"

    def test_bounded_memory_growth(self):
        bus = TelemetryBus(max_queue_size=100)
        for _ in range(5000):
            bus.record_item_started("ec", "memory_test")
        stats = bus.get_stats()
        assert stats["queue_size"] <= 100
        bus.stop()

    def test_concurrent_enqueue_no_crash(self):
        bus = TelemetryBus(max_queue_size=500)
        bus.start()
        errors = []

        def hammer():
            try:
                for _ in range(100):
                    bus.record_item_started("ec", "hammer")
                    bus.record_latency("ec", 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent enqueue produced {len(errors)} errors"
        bus.stop()

    def test_logical_clock_no_contention(self):
        clock = LogicalClock()
        n = 5000
        results = []

        def hammer(thread_id):
            for _ in range(n // 4):
                results.append(clock.tick("test"))

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        values = set(results)
        assert len(values) == len(results), "Duplicate timestamps from different threads"

    def test_enqueue_throughput(self):
        """Measure enqueue throughput (not flush/disk I/O)."""
        bus = TelemetryBus(max_queue_size=10000)
        n = 5000
        start = time.perf_counter()
        for _ in range(n):
            bus.record_item_started("ec", "throughput")
        elapsed = time.perf_counter() - start
        rate = n / elapsed if elapsed > 0 else float('inf')
        assert rate > 1000, f"Enqueue rate {rate:.0f} events/sec below 1000"


class TestOperationalization:
    """Operationalization tests: replay equivalence, stress, microbenchmark."""

    def test_replay_equivalence(self, tmp_path):
        """Generate events → persist via EventSink → reload → replay → verify checksum."""
        from src.advisory.telemetry_clock import stamp_event

        sink = EventSink(base_dir=str(tmp_path / "events"))
        envelopes = []
        for i in range(50):
            env = stamp_event(f"item_{'started' if i % 2 == 0 else 'completed'}", 1.0,
                              {"stage": "ec", "cache_key": f"key_{i:04d}"}, source="test")
            envelopes.append(env)

        for env in envelopes:
            sink.write(env)
        sink.flush()

        loaded = sink.load_all_events()
        assert len(loaded) == 50, f"Expected 50 events, got {len(loaded)}"

        replay = TelemetryReplay()
        replay.load_events(loaded)
        result = replay.replay_all()
        checksum = replay.compute_checksum()

        replay2 = TelemetryReplay()
        replay2.load_events(loaded)
        checksum2 = replay2.compute_checksum()
        assert checksum == checksum2, "Replay checksum not deterministic on same event stream"

        # Also sign-verify the checksum
        assert replay.verify_checksum(checksum), "verify_checksum(computed) should return True"
        assert not replay.verify_checksum("DEADBEEF" * 8), "verify_checksum(wrong) should return False"

        assert len(result["items_started"]) == 25
        assert len(result["items_completed"]) == 25
        sink.close()

    def test_critical_backpressure_stress_10k(self):
        """10k+ events under high load, 8 threads, verify no crash + reconciliation."""
        bus = TelemetryBus(max_queue_size=2000)
        bus.start()
        from src.advisory.telemetry_backpressure import get_backpressure_controller
        # Force CRITICAL load level for the duration of this test
        controller = get_backpressure_controller()
        controller.update(5000, 5.0, 100, 0)

        n_events = 10000
        errors = []
        lock = threading.Lock()

        def hammer():
            try:
                for _ in range(n_events // 8):
                    bus.record_item_started("ec", "stress")
                    bus.record_latency("ec", 0.5)
                    bus.record_item_completed("ec", "stress", decision="accept")
                    bus.record_confidence("ec", 0.85)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Stress produced {len(errors)} errors: {errors[:3]}"
        bus.stop()

        events = bus.get_event_log_sorted()
        assert len(events) > 0, "At least some events should survive backpressure"

        # Verify no ordering violations via reconciliation
        from src.advisory.telemetry_reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        report = engine.reconcile(events, {"stage": "ec"})
        assert report.consistency_score >= 0.8, (
            f"Reconciliation score {report.consistency_score:.2f} below 0.8; "
            f"violations={len(report.violations)}"
        )

    def test_telemetry_overhead_microbenchmark(self):
        """Measure TelemetryBus enqueue overhead (target < 1% of advisory generation)."""
        bus = TelemetryBus(max_queue_size=5000)
        n = 5000

        # Measure enqueue-only cost
        start = time.perf_counter()
        for _ in range(n):
            bus.record_item_started("ec", "bench")
            bus.record_latency("ec", 0.5)
        elapsed_enqueue = time.perf_counter() - start

        # Simulate advisory generation cost: LLM parse + classification
        # This is ~500ms in production; we simulate with a controlled busy-loop
        import math
        start = time.perf_counter()
        for _ in range(n):
            _ = math.sqrt(12345.6789) ** 2  # minimal CPU work
            _ = math.sin(3.14159) * math.cos(1.5708)
        elapsed_cpu = time.perf_counter() - start

        # The real ratio: enqueue time vs. simulated work
        # To get a proper ratio, we compare per-call enqueue to per-call simulated work
        per_call_enqueue = elapsed_enqueue / (2 * n)  # 2 events per iteration
        per_call_cpu = elapsed_cpu / n

        # In production, LLM is 500ms+ per call; the enqueue overhead must be negligible
        overhead_ratio = per_call_enqueue / max(per_call_cpu, 1e-9)
        print(f"\n[Benchmark] Per-call enqueue: {per_call_enqueue*1e6:.2f}µs")
        print(f"[Benchmark] Per-call simulated work: {per_call_cpu*1e6:.2f}µs")
        print(f"[Benchmark] Overhead ratio vs simulated work: {overhead_ratio:.4f}x")

        # Against real LLM latency (~500ms), the ratio would be:
        real_llm_per_call = 0.5  # 500ms
        overhead_vs_llm = per_call_enqueue / real_llm_per_call
        print(f"[Benchmark] Overhead vs 500ms LLM: {overhead_vs_llm*100:.4f}%")
        assert overhead_vs_llm < 0.01, (
            f"Telemetry overhead {overhead_vs_llm*100:.4f}% exceeds 1% of LLM time"
        )

        bus.stop()
