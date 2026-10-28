"""
Tests for SLA Management Engine — policy lookups, deadline calculation,
breach detection, escalation logic, and pause/resume accounting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from app.engine.sla import SLAEngine, get_sla_engine


@pytest.fixture
def sla_engine():
    return SLAEngine()


def test_sla_engine_singleton():
    """get_sla_engine returns the same object on repeated calls."""
    e1 = get_sla_engine()
    e2 = get_sla_engine()
    assert e1 is e2


def test_p1_policy_resolution_hours(sla_engine):
    """P1 SLA resolution window must be 4 hours per sla_config.yaml."""
    policy = sla_engine.get_policy("P1")
    assert policy.resolution_hours == 4.0


def test_p2_policy_resolution_hours(sla_engine):
    """P2 SLA resolution window must be 12 hours per sla_config.yaml."""
    policy = sla_engine.get_policy("P2")
    assert policy.resolution_hours == 12.0


def test_p3_policy_resolution_hours(sla_engine):
    """P3 SLA resolution window must be 48 hours per sla_config.yaml."""
    policy = sla_engine.get_policy("P3")
    assert policy.resolution_hours == 48.0


def test_p4_policy_resolution_hours(sla_engine):
    """P4 SLA resolution window must be 72 hours per sla_config.yaml."""
    policy = sla_engine.get_policy("P4")
    assert policy.resolution_hours == 72.0


def test_deadline_calculation(sla_engine):
    """Deadline = start_time + resolution_hours for each priority."""
    start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    for priority, hours in [("P1", 4), ("P2", 12), ("P3", 48), ("P4", 72)]:
        expected = start + timedelta(hours=hours)
        actual = sla_engine.calculate_deadline(start, priority)
        assert actual == expected, f"Deadline mismatch for {priority}"


def test_breach_detection_when_past_deadline(sla_engine):
    """evaluate_breach returns True when reference time exceeds deadline."""
    deadline = datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    after = datetime(2026, 6, 1, 15, 0, 0, tzinfo=timezone.utc)
    assert sla_engine.evaluate_breach(deadline, after) is True


def test_no_breach_when_before_deadline(sla_engine):
    """evaluate_breach returns False when reference time is before deadline."""
    deadline = datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    before = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert sla_engine.evaluate_breach(deadline, before) is False


def test_effective_elapsed_excludes_paused_time(sla_engine):
    """Effective elapsed must subtract accumulated paused hours."""
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    ref = start + timedelta(hours=10)
    elapsed = sla_engine.calculate_effective_elapsed(start, 3.0, ref)
    assert elapsed == pytest.approx(7.0)


def test_pause_extends_deadline(sla_engine):
    """Pausing should extend the current deadline by the paused duration."""
    original_deadline = datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    extended = sla_engine.adjust_deadline_for_pause(original_deadline, 2.0)
    assert extended == original_deadline + timedelta(hours=2)


def test_hours_remaining_positive(sla_engine):
    """Hours remaining is positive when time left before deadline."""
    deadline = datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    ref = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    remaining = sla_engine.get_hours_remaining(deadline, ref)
    assert remaining == pytest.approx(2.0)


def test_hours_remaining_negative_when_breached(sla_engine):
    """Hours remaining is negative after breach."""
    deadline = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    ref = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    remaining = sla_engine.get_hours_remaining(deadline, ref)
    assert remaining < 0


def test_escalation_triggered_after_threshold(sla_engine):
    """check_escalation_needed returns True past escalation threshold."""
    threshold = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    after_threshold = datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    assert sla_engine.check_escalation_needed(threshold, after_threshold) is True


def test_escalation_not_triggered_before_threshold(sla_engine):
    """check_escalation_needed returns False before threshold."""
    threshold = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    before = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert sla_engine.check_escalation_needed(threshold, before) is False


def test_breach_risk_pct_at_deadline_is_100(sla_engine):
    """At exactly the deadline, breach risk percentage must be 100%."""
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    deadline = start + timedelta(hours=4)
    risk = sla_engine.get_breach_risk_pct(start, deadline, 0.0, deadline)
    assert risk == pytest.approx(100.0)


def test_breach_risk_pct_at_half_time(sla_engine):
    """At halfway through SLA window, risk should be around 50%."""
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    deadline = start + timedelta(hours=4)
    ref = start + timedelta(hours=2)
    risk = sla_engine.get_breach_risk_pct(start, deadline, 0.0, ref)
    assert risk == pytest.approx(50.0, abs=0.1)


def test_p1_first_response_hours(sla_engine):
    """P1 first response SLA must be 1 hour per sla_config.yaml."""
    policy = sla_engine.get_policy("P1")
    assert policy.first_response_hours == 1.0


def test_p1_escalation_hours(sla_engine):
    """P1 escalation threshold must be 2 hours per sla_config.yaml."""
    policy = sla_engine.get_policy("P1")
    assert policy.escalation_hours == 2.0
