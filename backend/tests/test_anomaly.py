"""
Tests for AnomalyDetector — all six scenarios and ground-truth evaluation.
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
    """Inject must produce exactly 6 anomaly records, one for each scenario."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    response = inject_anomalies(db_session, count=6)

    assert response.success is True
    assert response.injected_count == 6
    assert len(response.anomalies) == 6

    # Verify all 6 distinct anomaly types are present
    types = {a.anomaly_type for a in response.anomalies}
    expected_types = {
        "PRIORITY_MISMATCH",
        "SLA_BACKDATED",
        "SURVEY_BEFORE_CLOSURE",
        "DUPLICATE_ASSIGNMENT",
        "MISSING_STATUS_EVENT",
        "REFUND_WITHOUT_RESOLUTION",
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


def test_anomaly_priority_mismatch_scenario(db_session):
    """PRIORITY_MISMATCH: safety complaint must be detected with P3/P4 priority."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    pm = [a for a in result.anomalies if a.anomaly_type == "PRIORITY_MISMATCH"]
    assert len(pm) >= 1
    assert pm[0].severity == "high"


def test_anomaly_sla_backdated_scenario(db_session):
    """SLA_BACKDATED: detector must find SLA deadline set before complaint creation."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    sla_b = [a for a in result.anomalies if a.anomaly_type == "SLA_BACKDATED"]
    assert len(sla_b) >= 1


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


def test_anomaly_duplicate_assignment_scenario(db_session):
    """DUPLICATE_ASSIGNMENT: complaint with two simultaneous active assignments."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    da = [a for a in result.anomalies if a.anomaly_type == "DUPLICATE_ASSIGNMENT"]
    assert len(da) >= 1


def test_anomaly_missing_status_event_scenario(db_session):
    """MISSING_STATUS_EVENT: complaint without initial 'open' event must be detected."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    mse = [a for a in result.anomalies if a.anomaly_type == "MISSING_STATUS_EVENT"]
    assert len(mse) >= 1


def test_anomaly_refund_without_resolution_scenario(db_session):
    """REFUND_WITHOUT_RESOLUTION: refund status event without resolution record."""
    generator = DataGenerator(seed=20261022, scale="starter")
    data = generator.generate_all()
    load_all(db_session, data, clear_first=True)

    inject_anomalies(db_session, count=6)

    detector = AnomalyDetector(db_session)
    result = detector.detect()

    rwr = [a for a in result.anomalies if a.anomaly_type == "REFUND_WITHOUT_RESOLUTION"]
    assert len(rwr) >= 1


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



