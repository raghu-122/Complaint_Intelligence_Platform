"""
Validation Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ValidationFinding(BaseModel):
    category: str  # schema, chronology, arithmetic, business_rules, integrity
    check_name: str
    status: str  # pass, warn, fail
    message: str
    record_id: Optional[str] = None
    table_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationSummary(BaseModel):
    passed: int
    warned: int
    failed: int
    total: int
    execution_time_seconds: float = 0.0


class ValidationReport(BaseModel):
    summary: ValidationSummary
    findings: List[ValidationFinding]
    generated_at: datetime
