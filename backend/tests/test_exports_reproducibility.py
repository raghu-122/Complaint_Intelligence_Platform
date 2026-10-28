"""
Tests for BaselineExporter, CSVExporter, JSONExporter, and ReproducibilityEngine.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from app.exports.exporter import BaselineExporter, CSVExporter, JSONExporter, sha256_file
from app.generator.orchestrator import DataGenerator


@pytest.fixture
def small_dataset():
    """Generate a minimal starter dataset for export tests."""
    gen = DataGenerator(seed=20261022, scale="starter")
    return gen.generate_all()


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


def test_sha256_file_is_deterministic(tmp_path):
    """sha256_file must return the same hash for identical file content."""
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2
    assert len(h1) == 64  # sha-256 hex digest length


def test_sha256_file_differs_for_different_content(tmp_path):
    """sha256_file must produce different hashes for different content."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("content A")
    f2.write_text("content B")
    assert sha256_file(f1) != sha256_file(f2)


def test_csv_exporter_creates_files(small_dataset, tmp_path):
    """CSVExporter must create a CSV file for each entity."""
    exporter = CSVExporter(export_dir=tmp_path)
    exported = exporter.export_all(small_dataset)
    for name in ["complaints", "customers", "orders", "products"]:
        assert name in exported
        assert exported[name].exists()
        assert exported[name].suffix == ".csv"


def test_csv_exporter_has_correct_record_count(small_dataset, tmp_path):
    """CSV file for complaints must have correct row count (header + records)."""
    exporter = CSVExporter(export_dir=tmp_path)
    complaints_path = exporter.export_entity("complaints", small_dataset["complaints"])
    lines = complaints_path.read_text(encoding="utf-8").splitlines()
    # First line is header; subsequent lines are data
    assert len(lines) == len(small_dataset["complaints"]) + 1


def test_json_exporter_creates_valid_json(small_dataset, tmp_path):
    """JSONExporter must produce valid, non-empty JSON for each entity."""
    exporter = JSONExporter(export_dir=tmp_path)
    exported = exporter.export_all(small_dataset)
    for name, path in exported.items():
        if name == "summary":
            continue
        content = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(content, list)


def test_json_exporter_creates_summary_file(small_dataset, tmp_path):
    """JSON export must include a summary.json with record counts."""
    exporter = JSONExporter(export_dir=tmp_path)
    exporter.export_all(small_dataset)
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "record_counts" in summary
    assert summary["record_counts"]["complaints"] == len(small_dataset["complaints"])


def test_baseline_exporter_generates_manifest(small_dataset, tmp_path):
    """BaselineExporter must generate manifest.json with SHA-256 hashes."""
    exporter = BaselineExporter(base_dir=tmp_path)
    manifest = exporter.export_and_create_manifest(
        data=small_dataset, seed=20261022, scale="starter"
    )
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    assert "files" in manifest
    assert "record_counts" in manifest
    assert manifest["seed"] == 20261022
    assert manifest["scale"] == "starter"


def test_manifest_sha256_hashes_are_non_empty(small_dataset, tmp_path):
    """Core entity files in manifest must have 64-char SHA-256 hex digest and non-zero size."""
    exporter = BaselineExporter(base_dir=tmp_path)
    manifest = exporter.export_and_create_manifest(
        data=small_dataset, seed=20261022, scale="starter"
    )
    # Core entities that must always have data
    core_entities = {"complaints", "customers", "orders", "products", "agents", "teams"}
    for fname, meta in manifest["files"].items():
        assert len(meta["sha256"]) == 64, f"Short hash for {fname}: {meta['sha256']}"
        # Only assert non-zero bytes for core data entities (not summary.json or
        # potentially empty auxiliary tables like complaint_relationships)
        entity_name = fname.split("/")[-1].replace(".csv", "").replace(".json", "")
        if entity_name in core_entities:
            assert meta["bytes"] > 0, f"Empty export file for core entity: {fname}"


def test_same_seed_produces_identical_csv_hashes(tmp_path):
    """Identical seeds must produce bitwise-identical CSV and data JSON exports."""
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    gen1 = DataGenerator(seed=20261022, scale="starter")
    data1 = gen1.generate_all()
    exp1 = BaselineExporter(base_dir=run1_dir)
    manifest1 = exp1.export_and_create_manifest(data=data1, seed=20261022, scale="starter")

    gen2 = DataGenerator(seed=20261022, scale="starter")
    data2 = gen2.generate_all()
    exp2 = BaselineExporter(base_dir=run2_dir)
    manifest2 = exp2.export_and_create_manifest(data=data2, seed=20261022, scale="starter")

    for fname in manifest1["files"]:
        h1 = manifest1["files"][fname]["sha256"]
        h2 = manifest2["files"].get(fname, {}).get("sha256")
        assert h1 == h2, f"Hash mismatch for {fname}: {h1} != {h2}"


def test_different_seeds_produce_different_csv_hashes(tmp_path):
    """Different seeds must produce different CSV content for complaints."""
    run1_dir = tmp_path / "s1"
    run2_dir = tmp_path / "s2"

    gen1 = DataGenerator(seed=11111, scale="starter")
    data1 = gen1.generate_all()
    exp1 = BaselineExporter(base_dir=run1_dir)
    manifest1 = exp1.export_and_create_manifest(data=data1, seed=11111, scale="starter")

    gen2 = DataGenerator(seed=22222, scale="starter")
    data2 = gen2.generate_all()
    exp2 = BaselineExporter(base_dir=run2_dir)
    manifest2 = exp2.export_and_create_manifest(data=data2, seed=22222, scale="starter")

    h1 = manifest1["files"].get("csv/complaints.csv", {}).get("sha256")
    h2 = manifest2["files"].get("csv/complaints.csv", {}).get("sha256")
    assert h1 != h2, "Different seeds must not produce the same complaint data"


def test_reproducibility_engine_passes(tmp_path):
    """ReproducibilityEngine.run_check must pass when seed is the same."""
    from app.reproducibility.engine import ReproducibilityEngine

    # Generate and save baseline first
    gen = DataGenerator(seed=20261022, scale="starter")
    data = gen.generate_all()
    exporter = BaselineExporter(base_dir=tmp_path / "baseline")
    exporter.export_and_create_manifest(data=data, seed=20261022, scale="starter")

    manifest_path = tmp_path / "baseline" / "manifest.json"
    engine = ReproducibilityEngine(manifest_path=manifest_path)
    result = engine.run_check(seed=20261022, scale="starter")

    assert result["reproducible"] is True
    assert result["status"] == "SUCCESS"
    assert result["matched_files"] == result["total_files"]
    assert len(result["mismatches"]) == 0


def test_reproducibility_engine_fails_on_wrong_seed(tmp_path):
    """ReproducibilityEngine must report MISMATCH when different seed is used."""
    from app.reproducibility.engine import ReproducibilityEngine

    gen = DataGenerator(seed=20261022, scale="starter")
    data = gen.generate_all()
    exporter = BaselineExporter(base_dir=tmp_path / "baseline")
    exporter.export_and_create_manifest(data=data, seed=20261022, scale="starter")

    manifest_path = tmp_path / "baseline" / "manifest.json"
    engine = ReproducibilityEngine(manifest_path=manifest_path)
    result = engine.run_check(seed=99999, scale="starter")

    assert result["reproducible"] is False
    assert len(result["mismatches"]) > 0


def test_reproducibility_engine_missing_manifest(tmp_path):
    """ReproducibilityEngine must return ERROR status when manifest is missing."""
    from app.reproducibility.engine import ReproducibilityEngine

    missing = tmp_path / "nonexistent" / "manifest.json"
    engine = ReproducibilityEngine(manifest_path=missing)
    result = engine.run_check()

    assert result["status"] == "ERROR"
    assert result["reproducible"] is False


def test_reproducibility_report_markdown_generated(tmp_path):
    """run_check must produce a reproducibility_report.md file."""
    from app.reproducibility.engine import ReproducibilityEngine

    gen = DataGenerator(seed=20261022, scale="starter")
    data = gen.generate_all()
    exporter = BaselineExporter(base_dir=tmp_path / "baseline")
    exporter.export_and_create_manifest(data=data, seed=20261022, scale="starter")

    manifest_path = tmp_path / "baseline" / "manifest.json"
    engine = ReproducibilityEngine(manifest_path=manifest_path)
    engine.run_check(seed=20261022, scale="starter")

    report_path = tmp_path / "baseline" / "reproducibility_report.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Reproducibility" in content
    assert "PASS" in content


def test_sql_exporter_dump_and_import_integrity(tmp_path):
    """SQLExporter must dump database and verify 100% record and FK integrity on import."""
    import sqlite3
    from app.exports.exporter import SQLExporter

    # Create dummy source database with relational foreign keys
    src_db = tmp_path / "source.db"
    conn = sqlite3.connect(src_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL REFERENCES parent(id), value TEXT)")
    conn.execute("INSERT INTO parent VALUES (1, 'Alice'), (2, 'Bob')")
    conn.execute("INSERT INTO child VALUES (101, 1, 'Data A'), (102, 2, 'Data B')")
    conn.commit()
    conn.close()

    exporter = SQLExporter(export_dir=tmp_path / "sql_export")
    sql_file = exporter.export_database(db_path=src_db, output_filename="dump.sql")
    assert sql_file.exists()
    assert sql_file.stat().st_size > 0

    target_db = tmp_path / "target.db"
    result = exporter.import_and_verify(sql_path=sql_file, target_db_path=target_db, source_db_path=src_db)

    assert result["status"] == "PASS"
    assert result["table_count"] == 2
    assert result["counts_match"] is True
    assert result["fk_check_passed"] is True
    assert result["target_counts"]["parent"] == 2
    assert result["target_counts"]["child"] == 2

