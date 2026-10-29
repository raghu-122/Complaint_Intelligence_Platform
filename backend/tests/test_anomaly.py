"""
Tests for AnomalyDetector — all six required scenarios and ground-truth evaluation.

Required scenarios (per spec):
1. MISSING_CUSTOMER_RELATIONSHIP – complaint has no linked customer
2. RESOLUTION_BEFORE_CREATION   – resolved_at < created_at
3. SLA_PAUSE_RESUME_INCONSISTENCY – SLA resume event before matching pause
4. REPEAT_COMPLAINT_NOT_LINKED  – repeat complaint not linked to prior record
5. SURVEY_BEFORE_CLOSURE        – survey submitted before complaint was closed
6. SAFETY_LOW_PRIORITY          – PRODUCT_SAFETY complaint assigned P3/P4
"""
from __future__ import annotations

import pytest
from app.anomaly.detector import AnomalyDetector, inject_anomalies
from app.generator.orchestrator import DataGenerator
from app.generator.loader import load_all


def test_clean_data_has_no_anomalies(db_session):
    """Clean generated data must have zero anomalies detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    assert result.detected_count == 0
    assert result.anomalies == []


def test_inject_six_anomaly_scenarios(db_session):
    """Inject must produce exactly 6 anomaly records, one for each required scenario."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    response = inject_anomalies(db_session, count=6)

    assert response.success is True
    assert response.injected_count == 6
    assert len(response.anomalies) == 6

    # Verify all 6 required anomaly types are present
    types = {a.anomaly_type for a in response.anomalies}
    expected_types = {
        "MISSING_CUSTOMER_RELATIONSHIP",
        "RESOLUTION_BEFORE_CREATION",
        "SLA_PAUSE_RESUME_INCONSISTENCY",
        "REPEAT_COMPLAINT_NOT_LINKED",
        "SURVEY_BEFORE_CLOSURE",
        "SAFETY_LOW_PRIORITY",
    }
    assert types == expected_types


def test_detect_all_injected_anomalies(db_session):
    """After injection, detector must find all 6 injected anomalies."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    assert result.detected_count >= 6
    # All injected anomalies should be ground-truth flagged
    gt_anomalies = [a for a in result.anomalies if a.is_ground_truth]
    assert len(gt_anomalies) >= 6


def test_anomaly_detection_metrics(db_session):
    """After inject+detect cycle, precision, recall, and F1 must be valid floats."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert 0.0 <= result.f1_score <= 1.0
    assert result.ground_truth_count == 6


def test_anomaly_missing_customer_relationship_scenario(db_session):
    """MISSING_CUSTOMER_RELATIONSHIP: complaint with null customer FK must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    mcr = [a for a in result.anomalies if a.anomaly_type == "MISSING_CUSTOMER_RELATIONSHIP"]
    assert len(mcr) >= 1
    assert mcr[0].severity in ("high", "critical")


def test_anomaly_resolution_before_creation_scenario(db_session):
    """RESOLUTION_BEFORE_CREATION: resolved_at < created_at must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    rbc = [a for a in result.anomalies if a.anomaly_type == "RESOLUTION_BEFORE_CREATION"]
    assert len(rbc) >= 1


def test_anomaly_survey_before_closure_scenario(db_session):
    """SURVEY_BEFORE_CLOSURE: survey submitted on an open complaint must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    sbc = [a for a in result.anomalies if a.anomaly_type == "SURVEY_BEFORE_CLOSURE"]
    assert len(sbc) >= 1


def test_anomaly_sla_pause_resume_inconsistency_scenario(db_session):
    """SLA_PAUSE_RESUME_INCONSISTENCY: resume before pause must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    spri = [a for a in result.anomalies if a.anomaly_type == "SLA_PAUSE_RESUME_INCONSISTENCY"]
    assert len(spri) >= 1


def test_anomaly_repeat_complaint_not_linked_scenario(db_session):
    """REPEAT_COMPLAINT_NOT_LINKED: repeat complaint without relationship record must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    rcnl = [a for a in result.anomalies if a.anomaly_type == "REPEAT_COMPLAINT_NOT_LINKED"]
    assert len(rcnl) >= 1


def test_anomaly_safety_low_priority_scenario(db_session):
    """SAFETY_LOW_PRIORITY: PRODUCT_SAFETY complaint with P3/P4 priority must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    slp = [a for a in result.anomalies if a.anomaly_type == "SAFETY_LOW_PRIORITY"]
    assert len(slp) >= 1
    assert slp[0].severity == "high"


def test_anomaly_per_category_metrics(db_session):
    """Detector must calculate precision, recall, F1, TP, FP, FN per category."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    assert result.category_metrics is not None
    assert len(result.category_metrics) == 6
    for cat, metric in result.category_metrics.items():
        assert metric.true_positives == 1
        assert metric.false_positives == 0
        assert metric.false_negatives == 0
        assert metric.precision == 1.0
        assert metric.recall == 1.0
        assert metric.f1_score == 1.0


def test_detector_independence_from_ground_truth(db_session, monkeypatch, tmp_path):
    """The detector must detect anomalies based purely on DB state without any ground truth file."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    # Point ground truth directory to an empty temp dir where no ground truth files exist
    non_existent_gt = tmp_path / "empty_dir" / "ground_truth.json"
    from app.anomaly import detector as detector_mod
    monkeypatch.setattr(detector_mod, "_get_ground_truth_path", lambda: non_existent_gt)

    detector = AnomalyDetector(db_session)
    # detect_only performs pure DB scanning with zero ground truth access
    findings = detector.detect_only()

    assert len(findings) == 6
    found_types = {f.anomaly_type for f in findings}
    assert len(found_types) == 6


def test_ground_truth_csv_generation(db_session):
    """Injection must generate ground_truth.csv with entity, record_id, issue_type, field."""
    import csv
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    from app.anomaly.detector import _get_ground_truth_csv_path
    csv_path = _get_ground_truth_csv_path()
    assert csv_path.exists(), "ground_truth.csv must be created"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 6
    required_cols = {"entity", "record_id", "issue_type", "field"}
    assert required_cols.issubset(set(reader.fieldnames or []))
    for row in rows:
        assert row["entity"]
        assert row["issue_type"]
        assert row["field"]
