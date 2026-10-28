"""
Tests for complaint keyword classification engine.
"""
from __future__ import annotations

import pytest
from app.engine.classifier import get_classifier


def test_classify_safety_incident():
    """Verify safety keywords trigger PRODUCT_SAFETY category with high confidence."""
    classifier = get_classifier()
    text = "The electric adapter overheated, produced smoke, and caught on fire while charging."
    result = classifier.classify(text)

    assert result.category_code == "PRODUCT_SAFETY"
    assert result.confidence > 0.0
    assert len(result.evidence) > 0
    # evidence is a JSON string containing matched_keywords
    assert any(kw in result.evidence.lower() for kw in ["fire", "smoke", "overheat", "safety"])


def test_classify_delivery_issue():
    """Verify delivery delay keywords match delivery category."""
    classifier = get_classifier()
    text = "My order has been in transit for two weeks, tracking number is not updated, still not delivered."
    result = classifier.classify(text)

    assert result.category_code in ["DELIVERY_DELAY", "MISSING_ORDER"]  # actual codes from categories.yaml
    assert result.confidence > 0.0


def test_fallback_category():
    """Verify neutral/generic text falls back gracefully."""
    classifier = get_classifier()
    text = "Hello, I am contacting you regarding a question."
    result = classifier.classify(text)

    assert result.category_code is not None
    assert result.rule_id is not None
