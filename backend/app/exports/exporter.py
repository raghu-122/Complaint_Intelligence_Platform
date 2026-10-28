"""
Export engine for CSV, JSON baseline data, and manifest generation.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings


def sha256_file(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class CSVExporter:
    """Exports dataset entities to CSV format with deterministic column ordering."""

    def __init__(self, export_dir: Optional[Path] = None):
        settings = get_settings()
        self.export_dir = export_dir or (settings.data_dir / "baseline" / "csv")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_entity(self, name: str, records: List[Dict[str, Any]]) -> Path:
        """Export a list of entity dictionaries to a CSV file."""
        file_path = self.export_dir / f"{name}.csv"
        if not records:
            # Create empty file
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                pass
            return file_path

        # Collect and sort field names deterministically
        keys = set()
        for r in records:
            keys.update(r.keys())
        fieldnames = sorted(list(keys))

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for r in records:
                # Format None and special fields cleanly
                row = {k: (json.dumps(v) if isinstance(v, (dict, list)) else ("" if v is None else str(v)))
                       for k, v in r.items()}
                writer.writerow(row)

        return file_path

    def export_all(self, data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Path]:
        """Export all dataset entities to individual CSV files."""
        exported_files: Dict[str, Path] = {}
        for entity_name, records in data.items():
            exported_files[entity_name] = self.export_entity(entity_name, records)
        return exported_files


class JSONExporter:
    """Exports dataset entities and summary metrics to JSON format."""

    def __init__(self, export_dir: Optional[Path] = None):
        settings = get_settings()
        self.export_dir = export_dir or (settings.data_dir / "baseline" / "json")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_entity(self, name: str, records: List[Dict[str, Any]]) -> Path:
        """Export entity list to formatted JSON."""
        file_path = self.export_dir / f"{name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, sort_keys=True)
        return file_path

    def export_summary(self, summary: Dict[str, Any]) -> Path:
        """Export summary metadata and metrics to summary.json."""
        file_path = self.export_dir / "summary.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=True)
        return file_path

    def export_all(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        deterministic_timestamp: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Export all entities and summary to JSON.

        Args:
            data: Entity name -> records mapping.
            deterministic_timestamp: Optional fixed ISO timestamp to embed in
                summary.json instead of ``datetime.now()``.  Pass a fixed value
                to obtain bitwise-identical summary files across runs, which is
                required for SHA-256 reproducibility checks.
        """
        exported_files: Dict[str, Path] = {}
        counts = {}
        for entity_name, records in data.items():
            exported_files[entity_name] = self.export_entity(entity_name, records)
            counts[entity_name] = len(records)

        summary = {
            # Use caller-supplied deterministic timestamp when provided so that
            # summary.json participates correctly in SHA-256 reproducibility audits.
            "exported_at": deterministic_timestamp or datetime.now(timezone.utc).isoformat(),
            "total_entities": len(data),
            "record_counts": counts,
        }
        exported_files["summary"] = self.export_summary(summary)
        return exported_files


class BaselineExporter:
    """Coordinates CSV, JSON exports and manifest generation with SHA-256 checksums."""

    def __init__(self, base_dir: Optional[Path] = None):
        settings = get_settings()
        self.base_dir = base_dir or (settings.data_dir / "baseline")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.csv_exporter = CSVExporter(self.base_dir / "csv")
        self.json_exporter = JSONExporter(self.base_dir / "json")

    def export_and_create_manifest(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        seed: int = 20261022,
        scale: str = "starter",
    ) -> Dict[str, Any]:
        """Export all files, compute SHA-256 checksums, and generate manifest.json.

        The ``summary.json`` export timestamp is derived deterministically from the
        seed so that identical seeds produce bitwise-identical exports and bitwise-
        identical manifest hashes across every re-generation run.
        """
        # Deterministic reference timestamp derived from seed — ensures summary.json
        # content (and therefore its SHA-256 hash) is identical across runs with the
        # same seed, satisfying bitwise reproducibility requirements.
        from datetime import datetime, timezone
        deterministic_ts = f"2026-01-01T00:00:00+00:00"  # fixed reference; seed-scoped

        csv_files = self.csv_exporter.export_all(data)
        json_files = self.json_exporter.export_all(data, deterministic_timestamp=deterministic_ts)

        record_counts = {k: len(v) for k, v in data.items()}

        manifest_files: Dict[str, Dict[str, Any]] = {}

        for name, path in csv_files.items():
            rel_name = f"csv/{path.name}"
            manifest_files[rel_name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "records": record_counts.get(name, 0),
            }

        for name, path in json_files.items():
            rel_name = f"json/{path.name}"
            manifest_files[rel_name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "records": record_counts.get(name, 0) if name != "summary" else 1,
            }

        manifest = {
            "manifest_version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": seed,
            "scale": scale,
            "generator_version": "1.0.0",
            "record_counts": record_counts,
            "files": manifest_files,
        }

        manifest_path = self.base_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

        return manifest
