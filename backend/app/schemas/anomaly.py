"""
Anomaly detection and injection schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnomalyItem(BaseModel):
    anomaly_id: str
    anomaly_type: str
    description: str
    severity: str  # high, medium, low
    complaint_id: Optional[str] = None
    table_name: Optional[str] = None
    record_id: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    is_ground_truth: bool = False
    detected_at: Optional[datetime] = None


class AnomalyDetectionResult(BaseModel):
    detected_count: int
    ground_truth_count: int
    precision: float
    recall: float
    f1_score: float
    anomalies: List[AnomalyItem]


class InjectAnomalyRequest(BaseModel):
    count: int = Field(default=6, ge=1, le=50, description="Total number of anomalies to inject")


class InjectAnomalyResponse(BaseModel):
    success: bool
    injected_count: int
    anomalies: List[AnomalyItem]
    message: str
