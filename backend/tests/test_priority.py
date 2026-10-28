"""
Tests for deterministic rules-based priority engine.
"""
from __future__ import annotations

from decimal import Decimal
import pytest
from app.engine.priority import PriorityEngine, get_settings


def test_safety_incident_is_always_p1():
    """Safety incidents must strictly map to P1 under rule PR-001 regardless of other factors."""
    engine = PriorityEngine()
    decision = engine.calculate_priority(
        category_code="PRODUCT_SAFETY",
        is_safety_category=True,
        sentiment="positive",  # Even with positive sentiment
        order_total=Decimal("10.00"),  # Even with tiny order total
        customer_vulnerability_flag=False,
        prior_complaint_count=0,
    )

    assert decision.priority == "P1"
    assert decision.rule_applied == "PR-001"
    assert decision.is_safety is True


def test_sentiment_detection():
    """Verify keyword sentiment detection correctly assigns positive, negative, and neutral."""
    engine = PriorityEngine()

    neg_text = "I am furious, totally unacceptable, worst product ever broken and defective."
    s_label, s_score = engine.detect_sentiment(neg_text)
    assert s_label == "negative"
    assert s_score < 0.0

    pos_text = "Thank you very much, excellent customer service, appreciate your help!"
    s_label, s_score = engine.detect_sentiment(pos_text)
    assert s_label == "positive"
    assert s_score > 0.0

    neutral_text = "Please find attached document for order 12345."
    s_label, s_score = engine.detect_sentiment(neutral_text)
    assert s_label == "neutral"
    assert s_score == 0.0


def test_high_order_value_priority():
    """High value orders with negative sentiment receive elevated priority."""
    engine = PriorityEngine()
    decision = engine.calculate_priority(
        category_code="BILLING_ERROR",
        is_safety_category=False,
        sentiment="negative",
        order_total=Decimal("2500.00"),
        customer_vulnerability_flag=False,
        prior_complaint_count=0,
    )

    assert decision.priority in ["P1", "P2"]
    assert decision.rule_applied != "PR-001"
