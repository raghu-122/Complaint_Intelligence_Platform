"""
Complaint lifecycle engine — enforces valid status transitions.
"""
from __future__ import annotations

from app.models.complaint import VALID_TRANSITIONS


class LifecycleEngine:
    """Validates and manages complaint status transitions."""

    def is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """Return True if the transition is allowed."""
        allowed = VALID_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    def get_allowed_transitions(self, from_status: str) -> set[str]:
        """Return the set of allowed next statuses."""
        return VALID_TRANSITIONS.get(from_status, set())

    def can_reopen(self, status: str) -> bool:
        """Return True if the complaint can be reopened."""
        return "reopened" in VALID_TRANSITIONS.get(status, set())

    def can_resolve(self, status: str) -> bool:
        """Return True if the complaint can be resolved."""
        return "resolved" in VALID_TRANSITIONS.get(status, set())


_engine = LifecycleEngine()


def get_lifecycle_engine() -> LifecycleEngine:
    return _engine
