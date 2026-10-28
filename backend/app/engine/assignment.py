"""
Assignment engine — determines which team and agent should own a complaint.

Rules:
1. Safety incidents → SAFETY team (highest precedence)
2. Category specialization → matching team
3. Among eligible agents, assign to lowest open_complaint_count
4. Tie-breaker: lowest agent_id (deterministic)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings


@dataclass
class AssignmentDecision:
    team_code: str
    agent_id: Optional[str]
    rule_applied: str
    reason: str


class AssignmentEngine:
    """Deterministic assignment logic based on category, team specialization, and workload."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_settings().config_dir / "assignment_rules.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._teams = data["teams"]
        self._rules = sorted(data["assignment_rules"], key=lambda r: r["precedence"])

    def get_team_for_category(self, category_code: str, is_safety: bool) -> Optional[dict]:
        """Find the best team for a given complaint category."""
        # Safety first
        if is_safety:
            for team in self._teams:
                if team.get("safety_capable"):
                    return team
        # Specialization match
        for team in self._teams:
            if category_code in team.get("specializations", []):
                return team
        # Fall back to GENERAL
        for team in self._teams:
            if team["code"] == "GENERAL":
                return team
        return None

    def select_agent(
        self,
        team_code: str,
        agents: list[dict],  # list of {agent_id, open_complaint_count, is_active}
        priority: str,
    ) -> Optional[dict]:
        """
        Select the best available agent from the team.

        Selection criteria:
        1. Active agents only
        2. Lowest open_complaint_count
        3. Tie-break: lowest agent_id (alphabetical)
        """
        eligible = [
            a for a in agents
            if a.get("team_code") == team_code and a.get("is_active", True)
        ]
        if not eligible:
            return None
        # Sort by workload, then by agent_id for deterministic tie-breaking
        eligible.sort(key=lambda a: (a.get("open_complaint_count", 0), a["agent_id"]))
        return eligible[0]

    def assign(
        self,
        category_code: str,
        is_safety: bool,
        priority: str,
        agents: list[dict],
    ) -> AssignmentDecision:
        """Perform full assignment and return the decision."""
        team = self.get_team_for_category(category_code, is_safety)
        if team is None:
            return AssignmentDecision(
                team_code="GENERAL",
                agent_id=None,
                rule_applied="FALLBACK",
                reason="No matching team found; defaulted to GENERAL",
            )

        team_code = team["code"]

        # Safety validation
        if is_safety and not team.get("safety_capable"):
            return AssignmentDecision(
                team_code="SAFETY",
                agent_id=None,
                rule_applied="PR-001+ASSIGNMENT_SAFETY",
                reason="POLICY VIOLATION DETECTED: Safety incident must go to safety-capable team",
            )

        rule = "SPECIALIZATION_MATCH" if not is_safety else "SAFETY_FIRST"
        agent = self.select_agent(team_code, agents, priority)

        return AssignmentDecision(
            team_code=team_code,
            agent_id=agent["agent_id"] if agent else None,
            rule_applied=rule,
            reason=(
                f"Assigned to {team_code} team (specialization match for {category_code}). "
                f"Agent selected by minimum workload"
                + (f": {agent['agent_id']} with {agent.get('open_complaint_count', 0)} open cases" if agent else ": no eligible agent found")
                + "."
            ),
        )


# Module-level singleton
_engine: Optional[AssignmentEngine] = None


def get_assignment_engine() -> AssignmentEngine:
    global _engine
    if _engine is None:
        _engine = AssignmentEngine()
    return _engine
