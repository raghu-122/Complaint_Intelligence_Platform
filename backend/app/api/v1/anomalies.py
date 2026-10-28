"""
Anomalies API router.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.anomaly.detector import AnomalyDetector, inject_anomalies
from app.schemas.anomaly import (
    AnomalyDetectionResult, InjectAnomalyRequest, InjectAnomalyResponse
)

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=AnomalyDetectionResult)
@router.get("/detect", response_model=AnomalyDetectionResult)
def list_anomalies(db: Session = Depends(get_db)):
    """Scan database for known anomalies and data rule violations."""
    detector = AnomalyDetector(db)
    return detector.detect()


@router.post("/inject", response_model=InjectAnomalyResponse)
def inject_anomaly_records(
    request: Optional[InjectAnomalyRequest] = Body(default=None),
    db: Session = Depends(get_db),
):
    """Inject deliberate anomaly scenarios for detector testing and evaluation."""
    count = request.count if request and request.count else 6
    return inject_anomalies(db=db, count=count)

