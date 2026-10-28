"""
Anomaly detection and injection framework.

Defines 6 key anomaly patterns:
1. PRIORITY_MISMATCH: Safety incident classified with low priority (P3/P4)
2. SLA_BACKDATED: SLA deadline set in the past before complaint creation
3. SURVEY_BEFORE_CLOSURE: Survey submitted before complaint closure
4. DUPLICATE_ASSIGNMENT: Same complaint with multiple active/current assignments
5. MISSING_STATUS_EVENT: Complaint missing initial 'open' status event
6. REFUND_WITHOUT_RESOLUTION: Refund recorded in messages/events without resolution record
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.complaint import Complaint, ComplaintStatusEvent
from app.models.assignment import Assignment
from app.models.sla import SLAClock
from app.models.resolution import Resolution
from app.models.survey import Survey
from app.models.agent import Agent
from app.schemas.anomaly import AnomalyItem, AnomalyDetectionResult, InjectAnomalyResponse


def _get_ground_truth_path() -> Path:
    settings = get_settings()
    path = settings.data_dir / "anomalies" / "ground_truth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _is_gt(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    if not dt1 or not dt2:
        return False
    d1 = dt1.replace(tzinfo=None) if dt1.tzinfo else dt1
    d2 = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
    return d1 > d2


class AnomalyDetector:
    """Scans the database for data corruption, logic bypasses, and rule violations."""

    def __init__(self, db: Session):
        self.db = db

    def detect(self) -> AnomalyDetectionResult:
        """Run all detectors, collect detected anomalies, and evaluate against ground truth."""
        detected: List[AnomalyItem] = []

        detected.extend(self._detect_priority_mismatches())
        detected.extend(self._detect_sla_backdated())
        detected.extend(self._detect_survey_before_closure())
        detected.extend(self._detect_duplicate_assignments())
        detected.extend(self._detect_missing_status_events())
        detected.extend(self._detect_refund_without_resolution())

        # Load ground truth if exists
        gt_path = _get_ground_truth_path()
        ground_truth_map: Dict[str, dict] = {}
        ground_truth_ids: Dict[str, dict] = {}
        if gt_path.exists():
            try:
                with open(gt_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("anomalies", []):
                        if item.get("complaint_id"):
                            ground_truth_map[item["complaint_id"]] = item
                        if item.get("anomaly_id"):
                            ground_truth_ids[item["anomaly_id"]] = item
            except Exception:
                pass

        # Mark ground truth matches
        for item in detected:
            if (item.complaint_id and item.complaint_id in ground_truth_map) or (item.anomaly_id and item.anomaly_id in ground_truth_ids):
                item.is_ground_truth = True

        gt_count = max(len(ground_truth_map), len(ground_truth_ids))
        detected_count = len(detected)

        # Calculate metrics
        tp = sum(1 for d in detected if d.is_ground_truth)
        precision = round(tp / detected_count, 4) if detected_count > 0 else 1.0
        recall = round(tp / gt_count, 4) if gt_count > 0 else 1.0
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 1.0

        return AnomalyDetectionResult(
            detected_count=detected_count,
            ground_truth_count=gt_count,
            precision=precision,
            recall=recall,
            f1_score=f1,
            anomalies=detected,
        )

    def _detect_priority_mismatches(self) -> List[AnomalyItem]:
        results = []
        complaints = self.db.scalars(
            select(Complaint).where(
                and_(
                    (Complaint.category_code == "PRODUCT_SAFETY") | (Complaint.is_safety_incident == True),
                    Complaint.priority.in_(["P3", "P4"]),
                )
            )
        ).all()
        for c in complaints:
            results.append(AnomalyItem(
                anomaly_id=c.anomaly_id or f"ANOM-PRI-{c.complaint_id}",
                anomaly_type="PRIORITY_MISMATCH",
                description=f"Safety complaint {c.complaint_id} incorrectly categorized as {c.priority} instead of P1",
                severity="high",
                complaint_id=c.complaint_id,
                table_name="complaints",
                record_id=str(c.id),
                evidence={"category_code": c.category_code, "priority": c.priority},
                detected_at=datetime.now(timezone.utc),
            ))
        return results

    def _detect_sla_backdated(self) -> List[AnomalyItem]:
        results = []
        clocks = self.db.scalars(select(SLAClock)).all()
        for s in clocks:
            comp = self.db.get(Complaint, s.complaint_id_fk)
            if comp and _is_gt(s.start_time, s.original_deadline):
                results.append(AnomalyItem(
                    anomaly_id=s.anomaly_id or f"ANOM-SLA-{comp.complaint_id}",
                    anomaly_type="SLA_BACKDATED",
                    description=f"SLA deadline {s.original_deadline} is backdated before start time {s.start_time}",
                    severity="high",
                    complaint_id=comp.complaint_id,
                    table_name="sla_clocks",
                    record_id=str(s.id),
                    evidence={"start_time": s.start_time.isoformat(), "original_deadline": s.original_deadline.isoformat()},
                    detected_at=datetime.now(timezone.utc),
                ))
        return results

    def _detect_survey_before_closure(self) -> List[AnomalyItem]:
        results = []
        surveys = self.db.scalars(select(Survey)).all()
        for s in surveys:
            comp = self.db.get(Complaint, s.complaint_id_fk)
            if comp:
                is_violation = False
                if comp.status != "closed" and not comp.closed_at:
                    is_violation = True
                elif comp.closed_at and _is_gt(comp.closed_at, s.submitted_at):
                    is_violation = True
                elif s.submitted_before_closure:
                    is_violation = True

                if is_violation:
                    results.append(AnomalyItem(
                        anomaly_id=s.anomaly_id or f"ANOM-SRV-{comp.complaint_id}",
                        anomaly_type="SURVEY_BEFORE_CLOSURE",
                        description=f"Survey {s.survey_id} was submitted before complaint {comp.complaint_id} was closed",
                        severity="medium",
                        complaint_id=comp.complaint_id,
                        table_name="surveys",
                        record_id=str(s.id),
                        evidence={"submitted_at": s.submitted_at.isoformat() if s.submitted_at else "", "complaint_status": comp.status},
                        detected_at=datetime.now(timezone.utc),
                    ))
        return results

    def _detect_duplicate_assignments(self) -> List[AnomalyItem]:
        results = []
        complaints = self.db.scalars(select(Complaint)).all()
        for c in complaints:
            active = [a for a in c.assignments if a.is_current]
            if len(active) > 1:
                results.append(AnomalyItem(
                    anomaly_id=c.anomaly_id or f"ANOM-ASN-{c.complaint_id}",
                    anomaly_type="DUPLICATE_ASSIGNMENT",
                    description=f"Complaint {c.complaint_id} has {len(active)} concurrent active assignments",
                    severity="medium",
                    complaint_id=c.complaint_id,
                    table_name="assignments",
                    record_id=str(active[0].id),
                    evidence={"assignment_ids": [a.assignment_id for a in active]},
                    detected_at=datetime.now(timezone.utc),
                ))
        return results

    def _detect_missing_status_events(self) -> List[AnomalyItem]:
        results = []
        complaints = self.db.scalars(select(Complaint)).all()
        for c in complaints:
            if not c.status_events:
                results.append(AnomalyItem(
                    anomaly_id=c.anomaly_id or f"ANOM-EVT-{c.complaint_id}",
                    anomaly_type="MISSING_STATUS_EVENT",
                    description=f"Complaint {c.complaint_id} has no status history events at all",
                    severity="high",
                    complaint_id=c.complaint_id,
                    table_name="complaint_status_events",
                    record_id=str(c.id),
                    detected_at=datetime.now(timezone.utc),
                ))
            else:
                has_open = any(e.to_status == "open" for e in c.status_events)
                if not has_open:
                    results.append(AnomalyItem(
                        anomaly_id=c.anomaly_id or f"ANOM-EVT-{c.complaint_id}",
                        anomaly_type="MISSING_STATUS_EVENT",
                        description=f"Complaint {c.complaint_id} is missing its initial 'open' status event",
                        severity="high",
                        complaint_id=c.complaint_id,
                        table_name="complaint_status_events",
                        record_id=str(c.id),
                        evidence={"events_found": [e.to_status for e in c.status_events]},
                        detected_at=datetime.now(timezone.utc),
                    ))
        return results

    def _detect_refund_without_resolution(self) -> List[AnomalyItem]:
        results = []
        complaints = self.db.scalars(select(Complaint)).all()
        for c in complaints:
            # Check if any message or status event records a refund, but complaint has no Resolution records
            refund_claimed = False
            for e in c.status_events:
                if e.reason and "refund" in e.reason.lower():
                    refund_claimed = True
                    break
            for m in c.messages:
                if "refund" in m.body.lower() and m.sender_type == "agent" and "processed" in m.body.lower():
                    refund_claimed = True
                    break

            if refund_claimed and len(c.resolutions) == 0:
                results.append(AnomalyItem(
                    anomaly_id=c.anomaly_id or f"ANOM-REF-{c.complaint_id}",
                    anomaly_type="REFUND_WITHOUT_RESOLUTION",
                    description=f"Refund recorded for complaint {c.complaint_id} but no formal resolution record exists",
                    severity="high",
                    complaint_id=c.complaint_id,
                    table_name="resolutions",
                    record_id=str(c.id),
                    detected_at=datetime.now(timezone.utc),
                ))
        return results


def inject_anomalies(db: Session, count: int = 6) -> InjectAnomalyResponse:
    """
    Injects 6 distinct anomaly scenarios into the database and updates ground_truth.json.
    """
    complaints = db.scalars(select(Complaint).order_by(Complaint.id)).all()
    if len(complaints) < 6:
        return InjectAnomalyResponse(
            success=False,
            injected_count=0,
            anomalies=[],
            message="Database requires at least 6 complaints to inject anomalies.",
        )

    injected: List[AnomalyItem] = []
    used_complaint_ids = set()

    # Scenario 1: PRIORITY_MISMATCH
    # Find or update a complaint to safety category with P3 priority
    comp1 = next((c for c in complaints if c.complaint_id not in used_complaint_ids), complaints[0])
    used_complaint_ids.add(comp1.complaint_id)
    comp1.category_code = "PRODUCT_SAFETY"
    comp1.is_safety_incident = True
    comp1.priority = "P3"
    comp1.is_anomaly = True
    comp1.anomaly_id = "ANOM-001"
    comp1.anomaly_type = "PRIORITY_MISMATCH"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-001",
        anomaly_type="PRIORITY_MISMATCH",
        description="Safety complaint incorrectly prioritized as P3 instead of P1",
        severity="high",
        complaint_id=comp1.complaint_id,
        table_name="complaints",
        record_id=str(comp1.id),
        is_ground_truth=True,
    ))

    # Scenario 2: SLA_BACKDATED
    comp2 = next((c for c in complaints if c.complaint_id not in used_complaint_ids and c.sla_clock is not None), complaints[1])
    used_complaint_ids.add(comp2.complaint_id)
    if comp2.sla_clock:
        backdated_time = comp2.created_at - timedelta(hours=48)
        comp2.sla_clock.original_deadline = backdated_time
        comp2.sla_clock.current_deadline = backdated_time
        comp2.sla_clock.is_anomaly = True
        comp2.sla_clock.anomaly_id = "ANOM-002"
        comp2.is_anomaly = True
        comp2.anomaly_id = "ANOM-002"
        comp2.anomaly_type = "SLA_BACKDATED"
        injected.append(AnomalyItem(
            anomaly_id="ANOM-002",
            anomaly_type="SLA_BACKDATED",
            description="SLA deadline set in the past before complaint creation time",
            severity="high",
            complaint_id=comp2.complaint_id,
            table_name="sla_clocks",
            record_id=str(comp2.sla_clock.id),
            is_ground_truth=True,
        ))

    # Scenario 3: SURVEY_BEFORE_CLOSURE
    comp3 = next((c for c in complaints if c.complaint_id not in used_complaint_ids), complaints[2])
    used_complaint_ids.add(comp3.complaint_id)
    comp3.status = "open"
    comp3.closed_at = None
    comp3.is_anomaly = True
    comp3.anomaly_id = "ANOM-003"
    comp3.anomaly_type = "SURVEY_BEFORE_CLOSURE"
    # Create survey submitted immediately
    survey = Survey(
        survey_id=f"SRV-ANOM-{comp3.complaint_id}",
        complaint_id_fk=comp3.id,
        rating=5,
        feedback="Survey submitted prematurely while case is still open.",
        submitted_by="system_test",
        submitted_before_closure=True,
        is_anomaly=True,
        anomaly_id="ANOM-003",
        submitted_at=comp3.created_at + timedelta(minutes=10),
        created_at=datetime.now(timezone.utc),
    )
    db.add(survey)
    injected.append(AnomalyItem(
        anomaly_id="ANOM-003",
        anomaly_type="SURVEY_BEFORE_CLOSURE",
        description="Customer satisfaction survey submitted before complaint was closed",
        severity="medium",
        complaint_id=comp3.complaint_id,
        table_name="surveys",
        is_ground_truth=True,
    ))

    # Scenario 4: DUPLICATE_ASSIGNMENT
    comp4 = next((c for c in complaints if c.complaint_id not in used_complaint_ids and len(c.assignments) > 0), complaints[3])
    used_complaint_ids.add(comp4.complaint_id)
    agents = db.scalars(select(Agent)).all()
    second_agent = agents[1] if len(agents) > 1 else agents[0]
    extra_asn = Assignment(
        assignment_id=f"ASN-DUP-{comp4.complaint_id}",
        complaint_id_fk=comp4.id,
        team_id_fk=second_agent.team_id_fk,
        agent_id_fk=second_agent.id,
        assignment_type="initial",
        assigned_by="system",
        reason="Duplicate concurrent assignment anomaly",
        rule_applied="ANOMALY_INJECTION",
        is_current=True,
        assigned_at=datetime.now(timezone.utc),
    )
    db.add(extra_asn)
    comp4.is_anomaly = True
    comp4.anomaly_id = "ANOM-004"
    comp4.anomaly_type = "DUPLICATE_ASSIGNMENT"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-004",
        anomaly_type="DUPLICATE_ASSIGNMENT",
        description="Complaint assigned to two agents simultaneously with is_current=True",
        severity="medium",
        complaint_id=comp4.complaint_id,
        table_name="assignments",
        is_ground_truth=True,
    ))

    # Scenario 5: MISSING_STATUS_EVENT
    comp5 = next((c for c in complaints if c.complaint_id not in used_complaint_ids and len(c.status_events) > 0), complaints[4])
    used_complaint_ids.add(comp5.complaint_id)
    # Delete 'open' event
    for evt in list(comp5.status_events):
        if evt.to_status == "open":
            db.delete(evt)
    comp5.is_anomaly = True
    comp5.anomaly_id = "ANOM-005"
    comp5.anomaly_type = "MISSING_STATUS_EVENT"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-005",
        anomaly_type="MISSING_STATUS_EVENT",
        description="Complaint has lifecycle events but lacks the initial 'open' status event",
        severity="high",
        complaint_id=comp5.complaint_id,
        table_name="complaint_status_events",
        is_ground_truth=True,
    ))

    # Scenario 6: REFUND_WITHOUT_RESOLUTION
    comp6 = next((c for c in complaints if c.complaint_id not in used_complaint_ids), complaints[5])
    used_complaint_ids.add(comp6.complaint_id)
    # Remove any existing resolutions
    for res in list(comp6.resolutions):
        db.delete(res)
    # Add a status event recording refund
    db.add(ComplaintStatusEvent(
        complaint_id_fk=comp6.id,
        from_status="in_progress",
        to_status="resolved",
        changed_by="agent",
        reason="Refund of $149.99 processed and issued to customer",
        occurred_at=comp6.created_at + timedelta(hours=5),
    ))
    comp6.status = "resolved"
    comp6.resolved_at = comp6.created_at + timedelta(hours=5)
    comp6.is_refund_pending = False
    comp6.is_anomaly = True
    comp6.anomaly_id = "ANOM-006"
    comp6.anomaly_type = "REFUND_WITHOUT_RESOLUTION"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-006",
        anomaly_type="REFUND_WITHOUT_RESOLUTION",
        description="Refund recorded in status event but no formal Resolution record exists",
        severity="high",
        complaint_id=comp6.complaint_id,
        table_name="resolutions",
        is_ground_truth=True,
    ))

    db.commit()

    # Save to ground_truth.json
    gt_path = _get_ground_truth_path()
    gt_payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_anomalies": len(injected),
        "anomalies": [item.model_dump(mode="json") for item in injected],
    }
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_payload, f, indent=2)

    return InjectAnomalyResponse(
        success=True,
        injected_count=len(injected),
        anomalies=injected,
        message=f"Successfully injected {len(injected)} anomalies and saved ground truth to {gt_path.name}",
    )
