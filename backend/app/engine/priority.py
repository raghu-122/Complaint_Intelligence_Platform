"""
Priority engine — deterministic, rules-based complaint prioritization.

Rules are applied in precedence order (lower number = higher priority).
Rule PR-001 (safety incident) can never be overridden by subsequent rules.

IMPORTANT: These rules and thresholds are project assumptions for the YottaFlex
code challenge. They are NOT official YottaFlex business thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings


PRIORITY_ORDER = ["P1", "P2", "P3", "P4"]


def priority_level(code: str) -> int:
    """Return numeric level (1=highest, 4=lowest)."""
    mapping = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    return mapping.get(code, 3)


def upgrade_priority(code: str, levels: int) -> str:
    """Upgrade priority by N levels (cannot go above P1)."""
    idx = PRIORITY_ORDER.index(code)
    new_idx = max(0, idx - levels)
    return PRIORITY_ORDER[new_idx]


@dataclass
class PriorityDecision:
    priority: str
    rule_applied: str
    explanation: str
    sentiment: str
    is_safety: bool


class PriorityEngine:
    """Applies business rules to assign P1-P4 priority."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_settings().config_dir / "priority_rules.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
        self._negative_kws = set(
            kw.lower() for kw in self._config["sentiment_thresholds"]["negative_keywords"]
        )
        self._positive_kws = set(
            kw.lower() for kw in self._config["sentiment_thresholds"]["positive_keywords"]
        )

    def detect_sentiment(self, text: str) -> tuple[str, float]:
        """
        Detect sentiment from text using keyword counts.

        Returns:
            (sentiment_label, sentiment_score)
            sentiment_label: 'positive', 'neutral', or 'negative'
            sentiment_score: -1.0 to 1.0
        """
        lower = text.lower()
        neg_count = sum(1 for kw in self._negative_kws if kw in lower)
        pos_count = sum(1 for kw in self._positive_kws if kw in lower)

        if neg_count > pos_count:
            score = -min(1.0, neg_count * 0.2)
            return "negative", round(score, 3)
        elif pos_count > neg_count:
            score = min(1.0, pos_count * 0.2)
            return "positive", round(score, 3)
        else:
            return "neutral", 0.0

    def calculate_priority(
        self,
        category_code: str,
        is_safety_category: bool,
        sentiment: str,
        order_total: Optional[Decimal],
        customer_vulnerability_flag: bool,
        prior_complaint_count: int,
    ) -> PriorityDecision:
        """
        Apply priority rules in precedence order.

        Args:
            category_code: Complaint category code
            is_safety_category: Whether the category has safety_risk=True
            sentiment: 'positive', 'neutral', or 'negative'
            order_total: Total order amount (None if no associated order)
            customer_vulnerability_flag: Synthetic vulnerability flag
            prior_complaint_count: Number of prior complaints from this customer

        Returns:
            PriorityDecision with priority, rule, and explanation
        """
        is_safety = is_safety_category
        order_value = float(order_total) if order_total is not None else 0.0

        # PR-001: Safety incident → always P1 (highest precedence, immutable)
        if is_safety:
            return PriorityDecision(
                priority="P1",
                rule_applied="PR-001",
                explanation=(
                    f"Safety incident detected (category={category_code}). "
                    "Safety incidents are always P1 per rule PR-001. "
                    "Cannot be overridden by order value, sentiment, or any other factor."
                ),
                sentiment=sentiment,
                is_safety=True,
            )

        # Determine base priority
        base_priority = "P3"  # default
        rule_applied = "PR-006"
        explanation_parts = [f"category={category_code}, sentiment={sentiment}"]

        # PR-002: Vulnerable customer + negative sentiment → P1
        if customer_vulnerability_flag and sentiment == "negative":
            base_priority = "P1"
            rule_applied = "PR-002"
            explanation_parts.append(
                "Vulnerable customer flag active with negative sentiment (PR-002)"
            )
        # PR-003: High order value (>500) + negative sentiment → P2
        elif order_value > 500 and sentiment == "negative":
            base_priority = "P2"
            rule_applied = "PR-003"
            explanation_parts.append(
                f"High order value (${order_value:.2f} > $500) with negative sentiment (PR-003)"
            )
        # PR-005: Medium order value + negative sentiment → P3
        elif 200 <= order_value <= 500 and sentiment == "negative":
            base_priority = "P3"
            rule_applied = "PR-005"
            explanation_parts.append(
                f"Medium order value (${order_value:.2f}) with negative sentiment (PR-005)"
            )
        # PR-006: Standard negative sentiment → P3
        elif sentiment == "negative":
            base_priority = "P3"
            rule_applied = "PR-006"
            explanation_parts.append("Standard complaint with negative sentiment (PR-006)")
        # PR-007: General inquiry or low severity with non-negative sentiment → P4
        else:
            base_priority = "P4"
            rule_applied = "PR-007"
            explanation_parts.append("Low severity / general inquiry with non-negative sentiment (PR-007)")

        # PR-004: Recurrence upgrade — applies after base priority is set
        final_priority = base_priority
        if prior_complaint_count >= 3 and base_priority != "P1":
            upgraded = upgrade_priority(base_priority, 1)
            explanation_parts.append(
                f"Upgraded from {base_priority} to {upgraded} due to recurrence "
                f"({prior_complaint_count} prior complaints, PR-004)"
            )
            final_priority = upgraded
            if rule_applied in ("PR-006", "PR-007"):
                rule_applied = "PR-004"
            else:
                rule_applied = f"{rule_applied}+PR-004"

        return PriorityDecision(
            priority=final_priority,
            rule_applied=rule_applied,
            explanation="; ".join(explanation_parts),
            sentiment=sentiment,
            is_safety=False,
        )


# Module-level singleton
_engine: Optional[PriorityEngine] = None


def get_priority_engine() -> PriorityEngine:
    global _engine
    if _engine is None:
        _engine = PriorityEngine()
    return _engine
