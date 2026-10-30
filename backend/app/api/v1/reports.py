"""
Reports API router.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.exports.exporter import sha256_file
from app.schemas.report import ReportFile, ReportListItem, ReportListResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline manifest not found. Please run generation first.",
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Baseline manifest could not be read.",
        ) from exc

    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Baseline manifest has an invalid format.",
        )
    return manifest


def _get_report_content(report_id: str, baseline_dir: Path, db: Session) -> Any:
    normalized_id = report_id.replace("-", "_")

    if normalized_id == "baseline_manifest":
        return _read_manifest(baseline_dir / "manifest.json")

    if normalized_id == "reproducibility_report":
        report_path = baseline_dir / "reproducibility_report.md"
        try:
            return report_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reproducibility report not found. Please run 'cli.py reproduce' first.",
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reproducibility report could not be read.",
            ) from exc

    if normalized_id == "validation_report":
        from app.api.v1.validate import get_validation

        return get_validation(category=None, status=None, db=db)

    if normalized_id == "anomaly_report":
        from app.api.v1.anomalies import list_anomalies

        return list_anomalies(db=db)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report '{report_id}' not found. See /api/v1/reports for available reports.",
    )


@router.get("", response_model=ReportListResponse)
def list_reports():
    """List available system reports and baseline export files with SHA-256 checksums."""
    settings = get_settings()
    baseline_dir = settings.data_dir / "baseline"
    manifest_path = baseline_dir / "manifest.json"
    repro_path = baseline_dir / "reproducibility_report.md"

    reports = [
        ReportListItem(
            report_id="baseline_manifest",
            title="Baseline Dataset Manifest",
            description="SHA-256 checksums, record counts, and generator metadata for baseline exports.",
            category="Dataset Baseline",
            format="json",
            url="/api/v1/reports/baseline_manifest",
            generated_at=datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc)
            if manifest_path.exists() else None,
        ),
        ReportListItem(
            report_id="reproducibility_report",
            title="Reproducibility Audit Report",
            description="Bitwise comparison of regenerated dataset files against baseline manifest hashes.",
            category="Determinism & Auditing",
            format="markdown",
            url="/api/v1/reports/reproducibility_report",
            generated_at=datetime.fromtimestamp(repro_path.stat().st_mtime, tz=timezone.utc)
            if repro_path.exists() else None,
        ),
        ReportListItem(
            report_id="validation_report",
            title="Data Quality & Integrity Report",
            description="Detailed findings across schema, chronology, arithmetic, business rules, and foreign keys.",
            category="Data Quality",
            format="json",
            generated_at=datetime.now(timezone.utc),
            url="/api/v1/reports/validation_report",
        ),
        ReportListItem(
            report_id="anomaly_report",
            title="Anomaly Detection & Ground Truth Report",
            description="Evaluation of anomaly detection precision, recall, and detected rule violations.",
            category="Anomaly Detection",
            format="json",
            generated_at=datetime.now(timezone.utc),
            url="/api/v1/reports/anomaly_report",
        ),
    ]

    files: list[ReportFile] = []
    manifest_map: dict[str, str] = {}
    if baseline_dir.exists():
        for file_path in sorted(baseline_dir.rglob("*")):
            if not file_path.is_file() or file_path.is_symlink() or file_path.name == ".gitkeep":
                continue
            relative_path = file_path.relative_to(baseline_dir).as_posix()
            stat = file_path.stat()
            files.append(
                ReportFile(
                    name=file_path.name,
                    path=relative_path,
                    size_bytes=stat.st_size,
                    type=file_path.suffix.lstrip(".").lower() or "file",
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    sha256=sha256_file(file_path),
                )
            )
        if manifest_path.exists():
            manifest = _read_manifest(manifest_path)
            manifest_map = {
                name: metadata.get("sha256", "")
                for name, metadata in manifest["files"].items()
                if isinstance(metadata, dict)
            }

    return ReportListResponse(
        reports=reports,
        total=len(reports),
        baseline_dir=str(baseline_dir),
        files=files,
        total_files=len(files),
        manifest=manifest_map,
    )


@router.get("/download")
def download_report_file(
    file: str = Query(..., description="Relative path within baseline dir, e.g. csv/agents.csv"),
):
    """Download a specific baseline export and include its SHA-256 checksum."""
    baseline_dir = (get_settings().data_dir / "baseline").resolve()
    candidate = baseline_dir / file
    if candidate.is_symlink():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    target = candidate.resolve()

    try:
        target.relative_to(baseline_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.") from exc

    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {file}")

    media_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".md": "text/markdown",
        ".sql": "application/sql",
        ".txt": "text/plain",
    }
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type=media_types.get(target.suffix.lower(), "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{target.name}"',
            "X-Checksum-SHA256": sha256_file(target),
        },
    )


@router.post("/export-baseline")
def export_baseline(
    scale: str = Query("starter", pattern="^(starter|full)$"),
    seed: int = Query(20261022),
):
    """Generate baseline export files and audit them without changing database records."""
    from app.exports.exporter import BaselineExporter
    from app.generator.orchestrator import DataGenerator
    from app.reproducibility.engine import ReproducibilityEngine

    data = DataGenerator(seed=seed, scale=scale).generate_all()
    exporter = BaselineExporter()
    manifest = exporter.export_and_create_manifest(data=data, seed=seed, scale=scale)
    del data

    audit = ReproducibilityEngine(
        manifest_path=exporter.base_dir / "manifest.json"
    ).run_check(seed=seed, scale=scale)
    if not audit["reproducible"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Baseline export failed its SHA-256 reproducibility check.",
        )

    return {
        "status": "success",
        "scale": scale,
        "seed": seed,
        "message": f"Successfully exported baseline files for scale '{scale}'",
        "manifest": manifest,
        "reproducibility": {
            "status": audit["status"],
            "matched_files": audit["matched_files"],
            "total_files": audit["total_files"],
        },
    }


@router.get("/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db)):
    """Download a system report as JSON or Markdown with a response checksum."""
    normalized_id = report_id.replace("-", "_")
    if normalized_id == "baseline_manifest":
        return download_report_file("manifest.json")
    if normalized_id == "reproducibility_report":
        return download_report_file("reproducibility_report.md")

    report = _get_report_content(report_id, get_settings().data_dir / "baseline", db)
    body = json.dumps(jsonable_encoder(report), indent=2, ensure_ascii=False).encode("utf-8")
    checksum = hashlib.sha256(body).hexdigest()
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{normalized_id}.json"',
            "X-Checksum-SHA256": checksum,
        },
    )


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Retrieve a specific system report by its report ID."""
    content = _get_report_content(report_id, get_settings().data_dir / "baseline", db)
    if report_id.replace("-", "_") == "reproducibility_report":
        return PlainTextResponse(content=content, media_type="text/markdown")
    return content
