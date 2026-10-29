"""
Reports API router.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import get_settings
from app.schemas.report import ReportFile, ReportListItem, ReportListResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_model=ReportListResponse)
def list_reports():
    """List all available system, audit, and reproducibility reports."""
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
            url="/api/v1/validate",
            generated_at=datetime.now(timezone.utc),
        ),
        ReportListItem(
            report_id="anomaly_report",
            title="Anomaly Detection & Ground Truth Report",
            description="Evaluation of anomaly detection precision, recall, and detected rule violations.",
            category="Anomaly Detection",
            format="json",
            url="/api/v1/anomalies",
            generated_at=datetime.now(timezone.utc),
        ),
    ]

    files: list[ReportFile] = []
    manifest_map: dict[str, str] = {}
    if baseline_dir.exists():
        for f in sorted(baseline_dir.rglob("*")):
            if f.is_file():
                rel_path = str(f.relative_to(baseline_dir)).replace("\\", "/")
                ext = f.suffix.lstrip(".").lower()
                stat = f.stat()
                files.append(
                    ReportFile(
                        name=f.name,
                        path=rel_path,
                        size_bytes=stat.st_size,
                        type=ext or "file",
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    )
                )
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
                    manifest_map = {
                        k: v.get("sha256", "") if isinstance(v, dict) else str(v)
                        for k, v in m_data.get("files", {}).items()
                    }
            except Exception:
                pass

    return ReportListResponse(
        reports=reports,
        total=len(reports),
        baseline_dir=str(baseline_dir),
        files=files,
        total_files=len(files),
        manifest=manifest_map,
    )


@router.get("/download")
def download_report_file(file: str = Query(..., description="Relative path within baseline dir, e.g. csv/agents.csv")):
    """Download a specific baseline export file by its relative path."""
    settings = get_settings()
    baseline_dir = (settings.data_dir / "baseline").resolve()

    # Security: resolve and ensure path stays within baseline_dir
    try:
        target = (baseline_dir / file).resolve()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path.")

    if not str(target).startswith(str(baseline_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {file}")

    # Determine media type
    suffix = target.suffix.lower()
    media_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


@router.get("/{report_id}")
def get_report(report_id: str):
    """Retrieve content of a specific report by report_id."""
    settings = get_settings()
    baseline_dir = settings.data_dir / "baseline"

    normalized_id = report_id.replace("-", "_")

    if normalized_id == "baseline_manifest":
        manifest_path = baseline_dir / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Baseline manifest not found. Please run generation first.",
            )
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    elif normalized_id == "reproducibility_report":
        repro_path = baseline_dir / "reproducibility_report.md"
        if not repro_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reproducibility report not found. Please run 'cli.py reproduce' first.",
            )
        with open(repro_path, "r", encoding="utf-8") as f:
            return PlainTextResponse(content=f.read(), media_type="text/markdown")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report '{report_id}' not found. See /api/v1/reports for available reports.",
    )
