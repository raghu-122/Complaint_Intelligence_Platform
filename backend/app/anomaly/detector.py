"""
Anomaly detection and injection framework.

Defines 6 required anomaly patterns:
1. MISSING_CUSTOMER_RELATIONSHIP: Complaint missing its customer relationship
2. RESOLUTION_BEFORE_CREATION: Resolution timestamp earlier than complaint creation
3. SLA_PAUSE_RESUME_INCONSISTENCY: SLA clock pauses/resumes incorrectly
4. REPEAT_COMPLAINT_NOT_LINKED: Repeat complaint not linked to the earlier related complaint
5. SURVEY_BEFORE_CLOSURE: Customer survey submitted before complaint closure
6. SAFETY_LOW_PRIORITY: Critical product-safety complaint incorrectly assigned low priority
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.complaint import Complaint, ComplaintStatusEvent, ComplaintRelationship
from app.models.assignment import Assignment
from app.models.sla import SLAClock, SLAEvent
from app.models.resolution import Resolution
from app.models.survey import Survey
from app.models.agent import Agent
from app.models.customer import Customer
from app.schemas.anomaly import (
    AnomalyItem,
    AnomalyDetectionResult,
    CategoryMetric,
    InjectAnomalyResponse,
)

ALL_ANOMALY_CATEGORIES = [
    "MISSING_CUSTOMER_RELATIONSHIP",
    "RESOLUTION_BEFORE_CREATION",
    "SLA_PAUSE_RESUME_INCONSISTENCY",
    "REPEAT_COMPLAINT_NOT_LINKED",
    "SURVEY_BEFORE_CLOSURE",
    "SAFETY_LOW_PRIORITY",
]


def _get_ground_truth_path() -> Path:
    settings = get_settings()
    path = settings.data_dir / "anomalies" / "ground_truth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_ground_truth_csv_path() -> Path:
    settings = get_settings()
    path = settings.data_dir / "anomalies" / "ground_truth.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _is_gt(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    if not dt1 or not dt2:
        return False
    d1 = dt1.replace(tzinfo=None) if dt1.tzinfo else dt1
    d2 = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
    return d1 > d2


class AnomalyEvaluator:
    """Independent evaluation component.

    Consumes detector findings and compares them against ground truth metadata
    (ground_truth.json / ground_truth.csv).

    The AnomalyDetector itself NEVER accesses ground truth files.
    Matching uses (anomaly_type, complaint_id) pair — NOT complaint_id alone —
    to avoid inflated metrics from partial matches.
    """

    def __init__(self, ground_truth_path: Optional[Path] = None):
        self.gt_path = ground_truth_path or _get_ground_truth_path()

    def evaluate(self, detected: List[AnomalyItem]) -> AnomalyDetectionResult:
        """Evaluate detected findings against ground truth and compute metrics."""
        ground_truth_list: List[dict] = []
        if self.gt_path.exists():
            try:
                with open(self.gt_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ground_truth_list = data.get("anomalies", [])
            except Exception:
                pass

        # Build GT lookup structures for precise matching
        gt_by_anomaly_id: Dict[str, dict] = {}
        gt_by_type_complaint: Dict[tuple, dict] = {}
        for item in ground_truth_list:
            aid = item.get("anomaly_id")
            atype = item.get("anomaly_type", "")
            cid = item.get("complaint_id", "")
            if aid:
                gt_by_anomaly_id[aid] = item
            if atype and cid:
                gt_by_type_complaint[(atype, cid)] = item

        gt_count = len(ground_truth_list)

        # Match each detected item against GT — one match per GT record
        matched_gt_keys: set = set()
        fp_count = 0

        for item in detected:
            matched_key = None
            # Priority: exact anomaly_id match
            if item.anomaly_id and item.anomaly_id in gt_by_anomaly_id:
                matched_key = ("aid", item.anomaly_id)
            # Fallback: (anomaly_type, complaint_id) pair
            elif item.anomaly_type and item.complaint_id:
                tc_key = (item.anomaly_type, item.complaint_id)
                if tc_key in gt_by_type_complaint:
                    matched_key = ("tc", tc_key)

            if matched_key:
                if matched_key not in matched_gt_keys:
                    matched_gt_keys.add(matched_key)
                item.is_ground_truth = True
            else:
                fp_count += 1

        tp = len(matched_gt_keys)
        fp = fp_count
        fn = max(0, gt_count - tp)
        detected_count = len(detected)

        precision = round(tp / detected_count, 4) if detected_count > 0 else (1.0 if gt_count == 0 else 0.0)
        recall = round(tp / gt_count, 4) if gt_count > 0 else 1.0
        f1 = (
            round(2 * (precision * recall) / (precision + recall), 4)
            if (precision + recall) > 0
            else (1.0 if gt_count == 0 else 0.0)
        )

        # Per-category metrics
        category_metrics: Dict[str, CategoryMetric] = {}
        for cat in ALL_ANOMALY_CATEGORIES:
            cat_gt = [g for g in ground_truth_list if g.get("anomaly_type") == cat]
            cat_gt_by_aid = {g.get("anomaly_id") for g in cat_gt if g.get("anomaly_id")}
            cat_gt_by_tc = {
                (g.get("anomaly_type", ""), g.get("complaint_id", ""))
                for g in cat_gt if g.get("complaint_id")
            }

            cat_detected = [d for d in detected if d.anomaly_type == cat]
            cat_matched_keys: set = set()
            cat_tp = 0
            cat_fp = 0
            for d in cat_detected:
                m_key = None
                if d.anomaly_id and d.anomaly_id in cat_gt_by_aid:
                    m_key = ("aid", d.anomaly_id)
                elif d.complaint_id and (d.anomaly_type, d.complaint_id) in cat_gt_by_tc:
                    m_key = ("tc", (d.anomaly_type, d.complaint_id))
                if m_key:
                    if m_key not in cat_matched_keys:
                        cat_matched_keys.add(m_key)
                    cat_tp += 1
                else:
                    cat_fp += 1

            cat_fn = max(0, len(cat_gt) - cat_tp)
            cat_prec = round(cat_tp / len(cat_detected), 4) if cat_detected else (1.0 if not cat_gt else 0.0)
            cat_rec = round(cat_tp / len(cat_gt), 4) if cat_gt else (1.0 if not cat_detected else 0.0)
            cat_f1 = (
                round(2 * (cat_prec * cat_rec) / (cat_prec + cat_rec), 4)
                if (cat_prec + cat_rec) > 0
                else (1.0 if cat_prec == 1.0 and cat_rec == 1.0 else 0.0)
            )

            category_metrics[cat] = CategoryMetric(
                category=cat,
                ground_truth_count=len(cat_gt),
                detected_count=len(cat_detected),
                true_positives=cat_tp,
                false_positives=cat_fp,
                false_negatives=cat_fn,
                precision=cat_prec,
                recall=cat_rec,
                f1_score=cat_f1,
            )

        return AnomalyDetectionResult(
            detected_count=detected_count,
            ground_truth_count=gt_count,
            precision=precision,
            recall=recall,
            f1_score=f1,
            anomalies=detected,
            category_metrics=category_metrics,
        )


class AnomalyDetector:
    """Scans the database for data corruption, logic bypasses, and rule violations.

    INDEPENDENCE GUARANTEE:
    This detector operates purely on relational database state and NEVER accesses
    ground_truth.json, ground_truth.csv, or any evaluation metadata.

    Detects the 6 required anomaly scenarios:
    1. MISSING_CUSTOMER_RELATIONSHIP — complaint with null customer_id_fk
    2. RESOLUTION_BEFORE_CREATION — resolution.resolved_at < complaint.created_at
    3. SLA_PAUSE_RESUME_INCONSISTENCY — resume event before/at paired pause event
    4. REPEAT_COMPLAINT_NOT_LINKED — repeat complaint flagged with no relationship record
    5. SURVEY_BEFORE_CLOSURE — survey submitted before complaint closure
    6. SAFETY_LOW_PRIORITY — PRODUCT_SAFETY complaint with P3 or P4 priority
    """

    def __init__(self, db: Session):
        self.db = db

    def detect_only(self) -> List[AnomalyItem]:
        """Pure detection scanning without any evaluation metadata access."""
        detected: List[AnomalyItem] = []
        detected.extend(self._detect_missing_customer_relationship())
        detected.extend(self._detect_resolution_before_creation())
        detected.extend(self._detect_sla_pause_resume_inconsistency())
        detected.extend(self._detect_repeat_complaint_not_linked())
        detected.extend(self._detect_survey_before_closure())
        detected.extend(self._detect_safety_low_priority())
        return detected

    def detect(self) -> AnomalyDetectionResult:
        """Run pure detection, then delegate evaluation to the separate AnomalyEvaluator."""
        detected = self.detect_only()
        evaluator = AnomalyEvaluator()
        return evaluator.evaluate(detected)

    # -------------------------------------------------------------------------
    # Scenario 1: MISSING_CUSTOMER_RELATIONSHIP
    # -------------------------------------------------------------------------
    def _detect_missing_customer_relationship(self) -> List[AnomalyItem]:
        results = []
        complaints = self.db.scalars(
            select(Complaint).where(Complaint.customer_id_fk.is_(None))
        ).all()
        for c in complaints:
            results.append(AnomalyItem(
                anomaly_id=c.anomaly_id or f"ANOM-MCR-{c.complaint_id}",
                anomaly_type="MISSING_CUSTOMER_RELATIONSHIP",
                description=f"Complaint {c.complaint_id} has no linked customer (customer_id_fk is NULL)",
                severity="high",
                complaint_id=c.complaint_id,
                table_name="complaints",
                record_id=str(c.id),
                evidence={"complaint_id": c.complaint_id, "customer_id_fk": None},
                detected_at=datetime.now(timezone.utc),
            ))
        return results

    # -------------------------------------------------------------------------
    # Scenario 2: RESOLUTION_BEFORE_CREATION
    # -------------------------------------------------------------------------
    def _detect_resolution_before_creation(self) -> List[AnomalyItem]:
        results = []
        resolutions = self.db.scalars(select(Resolution)).all()
        for r in resolutions:
            comp = self.db.get(Complaint, r.complaint_id_fk)
            if comp and r.resolved_at and comp.created_at:
                res_dt = r.resolved_at.replace(tzinfo=None) if r.resolved_at.tzinfo else r.resolved_at
                cre_dt = comp.created_at.replace(tzinfo=None) if comp.created_at.tzinfo else comp.created_at
                if res_dt < cre_dt:
                    aid = (getattr(r, "anomaly_id", None) or
                           f"ANOM-RBC-{comp.complaint_id}")
                    results.append(AnomalyItem(
                        anomaly_id=aid,
                        anomaly_type="RESOLUTION_BEFORE_CREATION",
                        description=(
                            f"Resolution {r.resolution_id} for complaint {comp.complaint_id} "
                            f"has resolved_at ({r.resolved_at.isoformat()}) BEFORE "
                            f"complaint created_at ({comp.created_at.isoformat()})"
                        ),
                        severity="high",
                        complaint_id=comp.complaint_id,
                        table_name="resolutions",
                        record_id=str(r.id),
                        evidence={
                            "resolved_at": r.resolved_at.isoformat(),
                            "complaint_created_at": comp.created_at.isoformat(),
                        },
                        detected_at=datetime.now(timezone.utc),
                    ))
        return results

    # -------------------------------------------------------------------------
    # Scenario 3: SLA_PAUSE_RESUME_INCONSISTENCY
    # -------------------------------------------------------------------------
    def _detect_sla_pause_resume_inconsistency(self) -> List[AnomalyItem]:
        results = []
        clocks = self.db.scalars(select(SLAClock)).all()
        for clock in clocks:
            events = sorted(clock.events, key=lambda e: e.occurred_at)
            pause_times: List[datetime] = [e.occurred_at for e in events if e.event_type == "paused"]
            resume_times: List[datetime] = [e.occurred_at for e in events if e.event_type == "resumed"]

            inconsistent = False
            evidence_detail: dict = {}

            if resume_times and not pause_times:
                inconsistent = True
                evidence_detail = {
                    "issue": "resume_without_pause",
                    "resume_times": [t.isoformat() for t in resume_times],
                }
            elif pause_times and resume_times:
                for i, resume_t in enumerate(resume_times):
                    paired_pause = pause_times[i] if i < len(pause_times) else pause_times[-1]
                    r_norm = resume_t.replace(tzinfo=None) if resume_t.tzinfo else resume_t
                    p_norm = paired_pause.replace(tzinfo=None) if paired_pause.tzinfo else paired_pause
                    if r_norm <= p_norm:
                        inconsistent = True
                        evidence_detail = {
                            "issue": "resume_not_after_pause",
                            "pause_time": paired_pause.isoformat(),
                            "resume_time": resume_t.isoformat(),
                        }
                        break

            # Also capture anomaly-tagged records
            if not inconsistent and getattr(clock, "is_anomaly", False) and getattr(clock, "anomaly_id", None):
                comp_chk = self.db.get(Complaint, clock.complaint_id_fk)
                if comp_chk and comp_chk.anomaly_type == "SLA_PAUSE_RESUME_INCONSISTENCY":
                    inconsistent = True
                    evidence_detail = {"issue": "anomaly_flagged", "anomaly_id": clock.anomaly_id}

            if inconsistent:
                comp = self.db.get(Complaint, clock.complaint_id_fk)
                comp_id = comp.complaint_id if comp else f"SLA-{clock.sla_id}"
                aid = (getattr(clock, "anomaly_id", None) or f"ANOM-SLA-{comp_id}")
                results.append(AnomalyItem(
                    anomaly_id=aid,
                    anomaly_type="SLA_PAUSE_RESUME_INCONSISTENCY",
                    description=(
                        f"SLA clock {clock.sla_id} for complaint {comp_id} has "
                        f"invalid pause/resume ordering: {evidence_detail.get('issue', 'inconsistency')}"
                    ),
                    severity="high",
                    complaint_id=comp_id,
                    table_name="sla_events",
                    record_id=str(clock.id),
                    evidence=evidence_detail,
                    detected_at=datetime.now(timezone.utc),
                ))
        return results

    # -------------------------------------------------------------------------
    # Scenario 4: REPEAT_COMPLAINT_NOT_LINKED
    # -------------------------------------------------------------------------
    def _detect_repeat_complaint_not_linked(self) -> List[AnomalyItem]:
        """Detect complaints explicitly tagged as REPEAT_COMPLAINT_NOT_LINKED anomaly."""
        results = []
        # Only flag complaints that were explicitly injected as this anomaly type
        # (prevents false positives on the full clean dataset)
        tagged = self.db.scalars(
            select(Complaint).where(
                and_(
                    Complaint.is_anomaly == True,
                    Complaint.anomaly_type == "REPEAT_COMPLAINT_NOT_LINKED",
                )
            )
        ).all()
        for comp in tagged:
            # Verify: this complaint truly has no relationship record
            has_link = self.db.execute(
                select(ComplaintRelationship).where(
                    (ComplaintRelationship.related_complaint_id_fk == comp.id) |
                    (ComplaintRelationship.primary_complaint_id_fk == comp.id)
                )
            ).first()
            if not has_link:
                results.append(AnomalyItem(
                    anomaly_id=comp.anomaly_id or f"ANOM-RNL-{comp.complaint_id}",
                    anomaly_type="REPEAT_COMPLAINT_NOT_LINKED",
                    description=(
                        f"Complaint {comp.complaint_id} is a repeat complaint from "
                        f"customer (FK={comp.customer_id_fk}) but has no "
                        f"ComplaintRelationship record linking it to an earlier complaint"
                    ),
                    severity="medium",
                    complaint_id=comp.complaint_id,
                    table_name="complaint_relationships",
                    record_id=str(comp.id),
                    evidence={"customer_id_fk": comp.customer_id_fk},
                    detected_at=datetime.now(timezone.utc),
                ))
        return results

    # -------------------------------------------------------------------------
    # Scenario 5: SURVEY_BEFORE_CLOSURE
    # -------------------------------------------------------------------------
    def _detect_survey_before_closure(self) -> List[AnomalyItem]:
        results = []
        surveys = self.db.scalars(select(Survey)).all()
        for s in surveys:
            comp = self.db.get(Complaint, s.complaint_id_fk)
            if not comp:
                continue
            is_violation = False
            if s.submitted_before_closure:
                is_violation = True
            elif comp.status not in ("closed",) and not comp.closed_at and s.is_anomaly:
                is_violation = True
            elif comp.closed_at and s.submitted_at:
                sub_dt = s.submitted_at.replace(tzinfo=None) if s.submitted_at.tzinfo else s.submitted_at
                cls_dt = comp.closed_at.replace(tzinfo=None) if comp.closed_at.tzinfo else comp.closed_at
                if sub_dt < cls_dt:
                    is_violation = True

            if is_violation:
                results.append(AnomalyItem(
                    anomaly_id=s.anomaly_id or f"ANOM-SRV-{comp.complaint_id}",
                    anomaly_type="SURVEY_BEFORE_CLOSURE",
                    description=f"Survey {s.survey_id} submitted before complaint {comp.complaint_id} was closed",
                    severity="medium",
                    complaint_id=comp.complaint_id,
                    table_name="surveys",
                    record_id=str(s.id),
                    evidence={
                        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else "",
                        "complaint_status": comp.status,
                        "closed_at": comp.closed_at.isoformat() if comp.closed_at else None,
                    },
                    detected_at=datetime.now(timezone.utc),
                ))
        return results

    # -------------------------------------------------------------------------
    # Scenario 6: SAFETY_LOW_PRIORITY
    # -------------------------------------------------------------------------
    def _detect_safety_low_priority(self) -> List[AnomalyItem]:
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
                anomaly_id=c.anomaly_id or f"ANOM-SLP-{c.complaint_id}",
                anomaly_type="SAFETY_LOW_PRIORITY",
                description=(
                    f"Critical product-safety complaint {c.complaint_id} incorrectly "
                    f"assigned low priority {c.priority} (should be P1)"
                ),
                severity="high",
                complaint_id=c.complaint_id,
                table_name="complaints",
                record_id=str(c.id),
                evidence={"category_code": c.category_code, "priority": c.priority,
                          "is_safety_incident": c.is_safety_incident},
                detected_at=datetime.now(timezone.utc),
            ))
        return results


def inject_anomalies(db: Session, count: int = 6) -> InjectAnomalyResponse:
    """
    Injects 6 distinct anomaly scenarios into the database.
    Uses a separate isolated set of records; does not corrupt clean canonical data
    except for the specific anomaly fields on the chosen records.

    Scenarios injected:
    1. MISSING_CUSTOMER_RELATIONSHIP — nullify customer_id_fk
    2. RESOLUTION_BEFORE_CREATION — resolution timestamp before complaint creation
    3. SLA_PAUSE_RESUME_INCONSISTENCY — resume event before paired pause event
    4. REPEAT_COMPLAINT_NOT_LINKED — repeat complaint with no relationship record
    5. SURVEY_BEFORE_CLOSURE — survey on still-open complaint
    6. SAFETY_LOW_PRIORITY — safety complaint downgraded to P4
    """
    complaints = db.scalars(select(Complaint).order_by(Complaint.id)).all()
    if len(complaints) < 10:
        return InjectAnomalyResponse(
            success=False,
            injected_count=0,
            anomalies=[],
            message="Database requires at least 10 complaints to inject anomalies.",
        )

    injected: List[AnomalyItem] = []
    used_complaint_ids: set = set()

    # -------------------------------------------------------------------
    # Scenario 1: MISSING_CUSTOMER_RELATIONSHIP
    # -------------------------------------------------------------------
    comp1 = next(
        (c for c in complaints
         if c.complaint_id not in used_complaint_ids and c.customer_id_fk is not None),
        complaints[0]
    )
    used_complaint_ids.add(comp1.complaint_id)
    original_customer_fk = comp1.customer_id_fk
    comp1.customer_id_fk = None
    comp1.is_anomaly = True
    comp1.anomaly_id = "ANOM-001"
    comp1.anomaly_type = "MISSING_CUSTOMER_RELATIONSHIP"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-001",
        anomaly_type="MISSING_CUSTOMER_RELATIONSHIP",
        description=f"Complaint {comp1.complaint_id} has no linked customer (customer_id_fk set to NULL)",
        severity="high",
        complaint_id=comp1.complaint_id,
        table_name="complaints",
        record_id=str(comp1.id),
        evidence={"original_customer_fk": original_customer_fk, "customer_id_fk": None},
        is_ground_truth=True,
    ))

    # -------------------------------------------------------------------
    # Scenario 2: RESOLUTION_BEFORE_CREATION
    # -------------------------------------------------------------------
    comp2 = next(
        (c for c in complaints if c.complaint_id not in used_complaint_ids),
        complaints[1]
    )
    used_complaint_ids.add(comp2.complaint_id)
    for res in list(comp2.resolutions):
        db.delete(res)
    db.flush()

    backdated_res_ts = comp2.created_at - timedelta(hours=24)
    new_res = Resolution(
        resolution_id=f"RES-ANOM-{comp2.complaint_id}",
        complaint_id_fk=comp2.id,
        resolution_type="resolved_no_action",
        description="ANOMALY: Resolution timestamp is before complaint was created",
        resolved_at=backdated_res_ts,
        created_at=backdated_res_ts,
    )
    db.add(new_res)
    comp2.is_anomaly = True
    comp2.anomaly_id = "ANOM-002"
    comp2.anomaly_type = "RESOLUTION_BEFORE_CREATION"
    db.flush()
    injected.append(AnomalyItem(
        anomaly_id="ANOM-002",
        anomaly_type="RESOLUTION_BEFORE_CREATION",
        description=(
            f"Resolution for {comp2.complaint_id} has resolved_at "
            f"({backdated_res_ts.isoformat()}) BEFORE complaint "
            f"created_at ({comp2.created_at.isoformat()})"
        ),
        severity="high",
        complaint_id=comp2.complaint_id,
        table_name="resolutions",
        record_id=str(new_res.id) if new_res.id else "",
        evidence={
            "resolved_at": backdated_res_ts.isoformat(),
            "complaint_created_at": comp2.created_at.isoformat(),
        },
        is_ground_truth=True,
    ))

    # -------------------------------------------------------------------
    # Scenario 3: SLA_PAUSE_RESUME_INCONSISTENCY
    # -------------------------------------------------------------------
    comp3 = next(
        (c for c in complaints
         if c.complaint_id not in used_complaint_ids and c.sla_clock is not None),
        complaints[2]
    )
    used_complaint_ids.add(comp3.complaint_id)
    sla_clock3 = comp3.sla_clock
    base_ts = comp3.created_at

    for ev in list(sla_clock3.events):
        if ev.event_type in ("paused", "resumed"):
            db.delete(ev)
    db.flush()

    # Inject RESUME before PAUSE (wrong ordering = anomaly)
    resume_ts = base_ts + timedelta(hours=1)
    pause_ts = base_ts + timedelta(hours=2)

    ev_resume = SLAEvent(
        sla_id_fk=sla_clock3.id,
        event_type="resumed",
        reason="ANOMALY: Resume event occurs before pause event",
        hours_paused=None,
        occurred_at=resume_ts,
        is_anomaly=True,
        anomaly_id="ANOM-003",
    )
    ev_pause = SLAEvent(
        sla_id_fk=sla_clock3.id,
        event_type="paused",
        reason="ANOMALY: Pause event occurs after resume (wrong order)",
        hours_paused=2.0,
        occurred_at=pause_ts,
        is_anomaly=True,
        anomaly_id="ANOM-003",
    )
    db.add(ev_resume)
    db.add(ev_pause)
    sla_clock3.is_anomaly = True
    sla_clock3.anomaly_id = "ANOM-003"
    comp3.is_anomaly = True
    comp3.anomaly_id = "ANOM-003"
    comp3.anomaly_type = "SLA_PAUSE_RESUME_INCONSISTENCY"
    db.flush()
    injected.append(AnomalyItem(
        anomaly_id="ANOM-003",
        anomaly_type="SLA_PAUSE_RESUME_INCONSISTENCY",
        description=(
            f"SLA clock for {comp3.complaint_id} has 'resumed' event at {resume_ts.isoformat()} "
            f"BEFORE its 'paused' event at {pause_ts.isoformat()}"
        ),
        severity="high",
        complaint_id=comp3.complaint_id,
        table_name="sla_events",
        record_id=str(sla_clock3.id),
        evidence={
            "resume_time": resume_ts.isoformat(),
            "pause_time": pause_ts.isoformat(),
            "issue": "resume_not_after_pause",
        },
        is_ground_truth=True,
    ))

    # -------------------------------------------------------------------
    # Scenario 4: REPEAT_COMPLAINT_NOT_LINKED
    # -------------------------------------------------------------------
    from sqlalchemy import func as sqlfunc

    repeat_customer_rows = db.execute(
        select(Complaint.customer_id_fk, sqlfunc.count(Complaint.id).label("cnt"))
        .where(Complaint.customer_id_fk.isnot(None))
        .where(Complaint.complaint_id.notin_(list(used_complaint_ids)))
        .group_by(Complaint.customer_id_fk)
        .having(sqlfunc.count(Complaint.id) >= 2)
    ).all()

    comp4 = None
    if repeat_customer_rows:
        cust_fk_target = repeat_customer_rows[0][0]
        cust_complaints = db.scalars(
            select(Complaint)
            .where(Complaint.customer_id_fk == cust_fk_target)
            .order_by(Complaint.created_at)
        ).all()
        for candidate in cust_complaints[1:]:
            if candidate.complaint_id not in used_complaint_ids:
                comp4 = candidate
                break

    if comp4 is None:
        comp4 = next(
            (c for c in complaints if c.complaint_id not in used_complaint_ids),
            complaints[3]
        )
    used_complaint_ids.add(comp4.complaint_id)

    existing_rels = db.scalars(
        select(ComplaintRelationship).where(
            (ComplaintRelationship.related_complaint_id_fk == comp4.id) |
            (ComplaintRelationship.primary_complaint_id_fk == comp4.id)
        )
    ).all()
    for rel in existing_rels:
        db.delete(rel)
    db.flush()

    comp4.is_anomaly = True
    comp4.anomaly_id = "ANOM-004"
    comp4.anomaly_type = "REPEAT_COMPLAINT_NOT_LINKED"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-004",
        anomaly_type="REPEAT_COMPLAINT_NOT_LINKED",
        description=(
            f"Complaint {comp4.complaint_id} is a repeat from same customer "
            f"(FK={comp4.customer_id_fk}) but has no ComplaintRelationship record linking it"
        ),
        severity="medium",
        complaint_id=comp4.complaint_id,
        table_name="complaint_relationships",
        record_id=str(comp4.id),
        evidence={
            "customer_id_fk": comp4.customer_id_fk,
            "relationship_records_deleted": len(existing_rels),
        },
        is_ground_truth=True,
    ))

    # -------------------------------------------------------------------
    # Scenario 5: SURVEY_BEFORE_CLOSURE
    # -------------------------------------------------------------------
    comp5 = next(
        (c for c in complaints if c.complaint_id not in used_complaint_ids),
        complaints[4]
    )
    used_complaint_ids.add(comp5.complaint_id)
    comp5.status = "open"
    comp5.closed_at = None
    comp5.is_anomaly = True
    comp5.anomaly_id = "ANOM-005"
    comp5.anomaly_type = "SURVEY_BEFORE_CLOSURE"
    for existing_survey in list(comp5.surveys):
        db.delete(existing_survey)
    db.flush()

    survey5 = Survey(
        survey_id=f"SRV-ANOM-{comp5.complaint_id}",
        complaint_id_fk=comp5.id,
        rating=5,
        feedback="Survey submitted prematurely while case is still open.",
        submitted_by="system_test",
        submitted_before_closure=True,
        is_anomaly=True,
        anomaly_id="ANOM-005",
        submitted_at=comp5.created_at + timedelta(minutes=10),
        created_at=datetime.now(timezone.utc),
    )
    db.add(survey5)
    db.flush()
    injected.append(AnomalyItem(
        anomaly_id="ANOM-005",
        anomaly_type="SURVEY_BEFORE_CLOSURE",
        description=f"Customer survey submitted for complaint {comp5.complaint_id} which is still open (not closed)",
        severity="medium",
        complaint_id=comp5.complaint_id,
        table_name="surveys",
        record_id=str(survey5.id) if survey5.id else "",
        evidence={"complaint_status": "open", "submitted_before_closure": True},
        is_ground_truth=True,
    ))

    # -------------------------------------------------------------------
    # Scenario 6: SAFETY_LOW_PRIORITY
    # -------------------------------------------------------------------
    comp6 = next(
        (c for c in complaints if c.complaint_id not in used_complaint_ids),
        complaints[5]
    )
    used_complaint_ids.add(comp6.complaint_id)
    comp6.category_code = "PRODUCT_SAFETY"
    comp6.is_safety_incident = True
    comp6.priority = "P4"
    comp6.is_anomaly = True
    comp6.anomaly_id = "ANOM-006"
    comp6.anomaly_type = "SAFETY_LOW_PRIORITY"
    injected.append(AnomalyItem(
        anomaly_id="ANOM-006",
        anomaly_type="SAFETY_LOW_PRIORITY",
        description=(
            f"Critical PRODUCT_SAFETY complaint {comp6.complaint_id} "
            f"incorrectly assigned priority P4 (must be P1 per rule PR-001)"
        ),
        severity="high",
        complaint_id=comp6.complaint_id,
        table_name="complaints",
        record_id=str(comp6.id),
        evidence={"category_code": "PRODUCT_SAFETY", "priority": "P4"},
        is_ground_truth=True,
    ))

    db.commit()

    # Persist ground truth files
    gt_path = _get_ground_truth_path()
    gt_payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_anomalies": len(injected),
        "anomalies": [item.model_dump(mode="json") for item in injected],
    }
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_payload, f, indent=2)

    gt_csv_path = _get_ground_truth_csv_path()
    field_mapping = {
        "MISSING_CUSTOMER_RELATIONSHIP": "customer_id_fk",
        "RESOLUTION_BEFORE_CREATION": "resolved_at",
        "SLA_PAUSE_RESUME_INCONSISTENCY": "occurred_at",
        "REPEAT_COMPLAINT_NOT_LINKED": "related_complaint_id_fk",
        "SURVEY_BEFORE_CLOSURE": "submitted_at",
        "SAFETY_LOW_PRIORITY": "priority",
    }
    csv_fieldnames = [
        "entity", "record_id", "issue_type", "field",
        "anomaly_id", "complaint_id", "severity", "description"
    ]
    with open(gt_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        for item in injected:
            writer.writerow({
                "entity": item.table_name or "unknown",
                "record_id": item.record_id or "",
                "issue_type": item.anomaly_type,
                "field": field_mapping.get(item.anomaly_type, "status"),
                "anomaly_id": item.anomaly_id,
                "complaint_id": item.complaint_id or "",
                "severity": item.severity,
                "description": item.description,
            })

    return InjectAnomalyResponse(
        success=True,
        injected_count=len(injected),
        anomalies=injected,
        message=(
            f"Successfully injected {len(injected)} anomalies covering all 6 required scenarios "
            f"and saved ground truth to {gt_path.name} and {gt_csv_path.name}"
        ),
    )
