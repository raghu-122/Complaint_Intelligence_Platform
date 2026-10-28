"""
SLA management engine.

Tracks SLA start, pause, resume, breach, and completion.
Time basis: elapsed hours (not business hours) for deterministic evaluation.
All timestamps are UTC.

IMPORTANT: SLA thresholds are project assumptions, not official YottaFlex SLAs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings


@dataclass
class SLAPolicy:
    priority: str
    resolution_hours: float
    escalation_hours: float
    first_response_hours: float


@dataclass
class SLAStatus:
    sla_id: str
    priority: str
    status: str
    start_time: datetime
    original_deadline: datetime
    current_deadline: datetime
    is_breached: bool
    is_escalated: bool
    accumulated_paused_hours: float
    effective_elapsed_hours: float
    hours_remaining: float
    breach_risk_pct: float


class SLAEngine:
    """Manages SLA lifecycle including pause/resume/breach detection."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_settings().config_dir / "sla_config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._policies: dict[str, SLAPolicy] = {}
        for p, cfg in data["policies"].items():
            self._policies[p] = SLAPolicy(
                priority=p,
                resolution_hours=cfg["resolution_hours"],
                escalation_hours=cfg["escalation_hours"],
                first_response_hours=cfg["first_response_hours"],
            )

    def get_policy(self, priority: str) -> SLAPolicy:
        return self._policies[priority]

    def calculate_deadline(self, start_time: datetime, priority: str) -> datetime:
        """Calculate SLA deadline from start time."""
        policy = self.get_policy(priority)
        return start_time + timedelta(hours=policy.resolution_hours)

    def calculate_escalation_threshold(self, start_time: datetime, priority: str) -> datetime:
        """Calculate when escalation should trigger."""
        policy = self.get_policy(priority)
        return start_time + timedelta(hours=policy.escalation_hours)

    def calculate_first_response_deadline(self, start_time: datetime, priority: str) -> datetime:
        """Calculate first response deadline."""
        policy = self.get_policy(priority)
        return start_time + timedelta(hours=policy.first_response_hours)

    def evaluate_breach(
        self,
        current_deadline: datetime,
        reference_time: Optional[datetime] = None,
    ) -> bool:
        """Check if SLA is breached at reference_time."""
        ref = reference_time or datetime.now(timezone.utc)
        return ref > current_deadline

    def calculate_effective_elapsed(
        self,
        start_time: datetime,
        accumulated_paused_hours: float,
        reference_time: Optional[datetime] = None,
    ) -> float:
        """Return elapsed hours excluding paused time."""
        ref = reference_time or datetime.now(timezone.utc)
        total_elapsed = (ref - start_time).total_seconds() / 3600
        return max(0.0, total_elapsed - accumulated_paused_hours)

    def adjust_deadline_for_pause(
        self,
        current_deadline: datetime,
        pause_hours: float,
    ) -> datetime:
        """Extend deadline by the paused duration."""
        return current_deadline + timedelta(hours=pause_hours)

    def check_escalation_needed(
        self,
        escalation_threshold_time: datetime,
        reference_time: Optional[datetime] = None,
    ) -> bool:
        """Return True if complaint should be escalated."""
        ref = reference_time or datetime.now(timezone.utc)
        return ref >= escalation_threshold_time

    def get_hours_remaining(
        self,
        current_deadline: datetime,
        reference_time: Optional[datetime] = None,
    ) -> float:
        """Return hours remaining until SLA breach (negative if breached)."""
        ref = reference_time or datetime.now(timezone.utc)
        delta = (current_deadline - ref).total_seconds() / 3600
        return round(delta, 2)

    def get_breach_risk_pct(
        self,
        start_time: datetime,
        current_deadline: datetime,
        accumulated_paused_hours: float,
        reference_time: Optional[datetime] = None,
    ) -> float:
        """Return percentage of SLA time elapsed (0-100+)."""
        ref = reference_time or datetime.now(timezone.utc)
        effective_elapsed = self.calculate_effective_elapsed(
            start_time, accumulated_paused_hours, ref
        )
        policy_hours = (current_deadline - start_time).total_seconds() / 3600
        if policy_hours <= 0:
            return 100.0
        return round(min(150.0, (effective_elapsed / policy_hours) * 100), 1)


# Module-level singleton
_engine: Optional[SLAEngine] = None


def get_sla_engine() -> SLAEngine:
    global _engine
    if _engine is None:
        _engine = SLAEngine()
    return _engine
