"""
Validation API router.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.validation.validator import ValidationEngine
from app.schemas.validation import ValidationReport

router = APIRouter(prefix="/validate", tags=["Validation"])


@router.post("", response_model=ValidationReport)
def run_validation(
    category: Optional[str] = Query(None, description="Optional domain filter: schema, chronology, arithmetic, business_rules, integrity"),
    status: Optional[str] = Query(None, description="Optional status filter: pass, warn, fail"),
    db: Session = Depends(get_db),
):
    """Run comprehensive database validation checks across all 5 verification domains."""
    engine = ValidationEngine(db)
    report = engine.run_all()
    if category or status:
        filtered_findings = [
            f for f in report.findings
            if (not category or f.category.lower() == category.lower())
            and (not status or f.status.lower() == status.lower())
        ]
        return ValidationReport(
            summary=report.summary,
            findings=filtered_findings,
            generated_at=report.generated_at,
        )
    return report


@router.get("", response_model=ValidationReport)
def get_validation(
    category: Optional[str] = Query(None, description="Optional domain filter: schema, chronology, arithmetic, business_rules, integrity"),
    status: Optional[str] = Query(None, description="Optional status filter: pass, warn, fail"),
    db: Session = Depends(get_db),
):
    """Run and return current validation status."""
    engine = ValidationEngine(db)
    report = engine.run_all()
    if category or status:
        filtered_findings = [
            f for f in report.findings
            if (not category or f.category.lower() == category.lower())
            and (not status or f.status.lower() == status.lower())
        ]
        return ValidationReport(
            summary=report.summary,
            findings=filtered_findings,
            generated_at=report.generated_at,
        )
    return report

