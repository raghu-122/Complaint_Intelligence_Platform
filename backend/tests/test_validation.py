"""
Tests for ValidationEngine data quality checks.
"""
from __future__ import annotations

import pytest
from app.validation.validator import ValidationEngine
from app.generator.orchestrator import DataGenerator
from app.generator.loader import load_all


def test_validation_on_clean_data(db_session):
    """Cleanly generated dataset must pass all data quality checks with 0 failures."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    engine = ValidationEngine(db_session)
    report = engine.run_all()

    assert report.summary.total > 0
    assert report.summary.failed == 0, f"Expected 0 failed checks, got {report.summary.failed}"
    assert report.summary.passed > 0

    # Ensure all 5 categories are represented
    categories = {f.category for f in report.findings}
    expected = {"schema", "chronology", "arithmetic", "business_rules", "integrity"}
    assert expected.issubset(categories)
