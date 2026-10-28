"""
Report schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ReportListItem(BaseModel):
    report_id: str
    title: str
    description: str
    category: str
    format: str  # json, csv, markdown
    generated_at: Optional[datetime] = None
    url: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ReportFile(BaseModel):
    name: str
    path: str
    size_bytes: int
    type: str
    modified_at: Optional[str] = None


class ReportListResponse(BaseModel):
    reports: List[ReportListItem] = []
    total: int = 0
    baseline_dir: Optional[str] = None
    files: List[ReportFile] = []
    total_files: int = 0
    manifest: Optional[Dict[str, str]] = None
