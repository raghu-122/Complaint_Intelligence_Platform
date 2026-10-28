"""
Validation Engine — comprehensive data quality and rule validation.

Implements:
1. schema_checks: required fields, types, and constraints
2. chronology_checks: timeline ordering across events and lifecycles
3. arithmetic_checks: numeric integrity (order totals, paused hours)
4. business_rule_checks: business policy enforcement (safety P1, SLA configs)
5. integrity_checks: referential integrity, orphaned records, unique constraints
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order
from app.models.complaint import Complaint, ComplaintStatusEvent, ComplaintRelationship
from app.models.message import ComplaintMessage
from app.models.assignment import Assignment
from app.models.sla import SLAClock, SLAEvent
from app.models.resolution import Resolution
from app.models.survey import Survey
from app.models.team import Team
from app.models.agent import Agent
from app.engine.sla import get_sla_engine
from app.schemas.validation import ValidationFinding, ValidationReport, ValidationSummary


def _is_gt(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    if not dt1 or not dt2:
        return False
    d1 = dt1.replace(tzinfo=None) if dt1.tzinfo else dt1
    d2 = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
    return d1 > d2


class ValidationEngine:
    """Runs data quality, integrity, and business logic checks against the database."""

    def __init__(self, db: Session):
        self.db = db
        self.sla_engine = get_sla_engine()

    def run_all(self) -> ValidationReport:
        """Run all validation check categories and compile report."""
        start_time = time.time()
        findings: List[ValidationFinding] = []

        findings.extend(self.schema_checks())
        findings.extend(self.chronology_checks())
        findings.extend(self.arithmetic_checks())
        findings.extend(self.business_rule_checks())
        findings.extend(self.integrity_checks())

        passed = sum(1 for f in findings if f.status == "pass")
        warned = sum(1 for f in findings if f.status == "warn")
        failed = sum(1 for f in findings if f.status == "fail")
        total = len(findings)

        summary = ValidationSummary(
            passed=passed,
            warned=warned,
            failed=failed,
            total=total,
            execution_time_seconds=round(time.time() - start_time, 4),
        )

        return ValidationReport(
            summary=summary,
            findings=findings,
            generated_at=datetime.now(timezone.utc),
        )

    # =========================================================================
    # 1. Schema Checks
    # =========================================================================
    def schema_checks(self) -> List[ValidationFinding]:
        findings = []

        # Complaints: required core fields
        complaints = self.db.scalars(select(Complaint)).all()
        invalid_complaints = [
            c.complaint_id for c in complaints
            if not c.complaint_id or not c.subject or not c.description or not c.status or not c.priority
        ]
        if invalid_complaints:
            findings.append(ValidationFinding(
                category="schema",
                check_name="complaint_required_fields",
                status="fail",
                message=f"Found {len(invalid_complaints)} complaints with missing required fields",
                table_name="complaints",
                details={"invalid_ids": invalid_complaints[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="complaint_required_fields",
                status="pass",
                message="All complaints have valid required fields",
                table_name="complaints",
            ))

        # Customers: valid email & name
        customers = self.db.scalars(select(Customer)).all()
        invalid_customers = [
            c.customer_id for c in customers
            if not c.customer_id or not c.first_name or not c.last_name or "@" not in (c.email or "")
        ]
        if invalid_customers:
            findings.append(ValidationFinding(
                category="schema",
                check_name="customer_required_fields",
                status="fail",
                message=f"Found {len(invalid_customers)} customers with invalid name or email format",
                table_name="customers",
                details={"invalid_ids": invalid_customers[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="customer_required_fields",
                status="pass",
                message="All customers have valid names and emails",
                table_name="customers",
            ))

        # Products: unit_price non-negative & non-empty SKU
        products = self.db.scalars(select(Product)).all()
        invalid_products = [
            p.product_id for p in products
            if not p.sku or (p.unit_price is not None and p.unit_price < 0)
        ]
        if invalid_products:
            findings.append(ValidationFinding(
                category="schema",
                check_name="product_constraints",
                status="fail",
                message=f"Found {len(invalid_products)} products with negative price or empty SKU",
                table_name="products",
                details={"invalid_ids": invalid_products[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="product_constraints",
                status="pass",
                message="All products satisfy pricing and SKU constraints",
                table_name="products",
            ))

        # Teams: valid JSON specializations
        teams = self.db.scalars(select(Team)).all()
        invalid_teams = []
        for t in teams:
            try:
                json.loads(t.specializations)
            except Exception:
                invalid_teams.append(t.team_id)
        if invalid_teams:
            findings.append(ValidationFinding(
                category="schema",
                check_name="team_json_serialization",
                status="fail",
                message=f"Found {len(invalid_teams)} teams with invalid JSON in specializations",
                table_name="teams",
                details={"invalid_ids": invalid_teams},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="team_json_serialization",
                status="pass",
                message="All team specializations contain valid JSON",
                table_name="teams",
            ))

        return findings

    # =========================================================================
    # 2. Chronology Checks
    # =========================================================================
    def chronology_checks(self) -> List[ValidationFinding]:
        findings = []

        # Complaints: created_at <= resolved_at <= closed_at
        complaints = self.db.scalars(select(Complaint)).all()
        chrono_violations = []
        for c in complaints:
            if c.resolved_at and c.created_at and _is_gt(c.created_at, c.resolved_at):
                chrono_violations.append({
                    "complaint_id": c.complaint_id,
                    "reason": f"created_at ({c.created_at}) > resolved_at ({c.resolved_at})",
                })
            elif c.closed_at and c.resolved_at and _is_gt(c.resolved_at, c.closed_at):
                chrono_violations.append({
                    "complaint_id": c.complaint_id,
                    "reason": f"resolved_at ({c.resolved_at}) > closed_at ({c.closed_at})",
                })
            elif c.closed_at and c.created_at and _is_gt(c.created_at, c.closed_at):
                chrono_violations.append({
                    "complaint_id": c.complaint_id,
                    "reason": f"created_at ({c.created_at}) > closed_at ({c.closed_at})",
                })

        if chrono_violations:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="complaint_lifecycle_timeline",
                status="fail",
                message=f"Found {len(chrono_violations)} complaints with inverted lifecycle timestamps",
                table_name="complaints",
                details={"violations": chrono_violations[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="complaint_lifecycle_timeline",
                status="pass",
                message="All complaints follow strict chronological progression (created <= resolved <= closed)",
                table_name="complaints",
            ))

        # Surveys: survey submitted_at >= complaint closed_at
        surveys = self.db.scalars(select(Survey)).all()
        survey_violations = []
        for s in surveys:
            comp = self.db.get(Complaint, s.complaint_id_fk)
            if comp:
                # If survey submitted before closed and not marked anomaly
                if not comp.closed_at:
                    if not s.is_anomaly:
                        survey_violations.append({
                            "survey_id": s.survey_id,
                            "complaint_id": comp.complaint_id,
                            "reason": "Survey submitted for unclosed complaint without anomaly flag",
                        })
                elif comp.closed_at and _is_gt(comp.closed_at, s.submitted_at) and not s.is_anomaly and not s.submitted_before_closure:
                    survey_violations.append({
                        "survey_id": s.survey_id,
                        "complaint_id": comp.complaint_id,
                        "reason": f"Survey submitted_at ({s.submitted_at}) < closed_at ({comp.closed_at})",
                    })

        if survey_violations:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="survey_submission_timing",
                status="fail",
                message=f"Found {len(survey_violations)} surveys submitted before complaint closure",
                table_name="surveys",
                details={"violations": survey_violations[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="survey_submission_timing",
                status="pass",
                message="All standard surveys were submitted post-closure",
                table_name="surveys",
            ))

        # Orders: ordered_at <= shipped_at <= delivered_at
        orders = self.db.scalars(select(Order)).all()
        order_violations = []
        for o in orders:
            if o.shipped_at and o.ordered_at and _is_gt(o.ordered_at, o.shipped_at):
                order_violations.append({
                    "order_id": o.order_id,
                    "reason": f"ordered_at ({o.ordered_at}) > shipped_at ({o.shipped_at})",
                })
            elif o.delivered_at and o.shipped_at and _is_gt(o.shipped_at, o.delivered_at):
                order_violations.append({
                    "order_id": o.order_id,
                    "reason": f"shipped_at ({o.shipped_at}) > delivered_at ({o.delivered_at})",
                })

        if order_violations:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="order_fulfillment_timeline",
                status="fail",
                message=f"Found {len(order_violations)} orders with inverted fulfillment timestamps",
                table_name="orders",
                details={"violations": order_violations[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="chronology",
                check_name="order_fulfillment_timeline",
                status="pass",
                message="All orders satisfy ordered <= shipped <= delivered",
                table_name="orders",
            ))

        return findings

    # =========================================================================
    # 3. Arithmetic Checks
    # =========================================================================
    def arithmetic_checks(self) -> List[ValidationFinding]:
        findings = []

        # Order totals: total_amount = unit_price * quantity - discount_amount
        orders = self.db.scalars(select(Order)).all()
        math_violations = []
        for o in orders:
            expected = (Decimal(str(o.unit_price)) * o.quantity) - Decimal(str(o.discount_amount or "0.00"))
            actual = Decimal(str(o.total_amount))
            if abs(actual - expected) >= Decimal("0.02"):
                math_violations.append({
                    "order_id": o.order_id,
                    "expected": str(expected),
                    "actual": str(actual),
                    "difference": str(actual - expected),
                })

        if math_violations:
            findings.append(ValidationFinding(
                category="arithmetic",
                check_name="order_total_calculation",
                status="fail",
                message=f"Found {len(math_violations)} orders where total != (unit_price * qty - discount)",
                table_name="orders",
                details={"violations": math_violations[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="arithmetic",
                check_name="order_total_calculation",
                status="pass",
                message="All order totals correctly match (unit_price * quantity - discount)",
                table_name="orders",
            ))

        # Non-negative SLA accumulated pause
        sla_clocks = self.db.scalars(select(SLAClock)).all()
        invalid_pauses = [
            s.sla_id for s in sla_clocks
            if s.accumulated_paused_hours is not None and s.accumulated_paused_hours < 0
        ]
        if invalid_pauses:
            findings.append(ValidationFinding(
                category="arithmetic",
                check_name="sla_paused_hours_non_negative",
                status="fail",
                message=f"Found {len(invalid_pauses)} SLA clocks with negative paused hours",
                table_name="sla_clocks",
                details={"invalid_ids": invalid_pauses},
            ))
        else:
            findings.append(ValidationFinding(
                category="arithmetic",
                check_name="sla_paused_hours_non_negative",
                status="pass",
                message="All SLA accumulated paused hours are non-negative",
                table_name="sla_clocks",
            ))

        return findings

    # =========================================================================
    # 4. Business Rule Checks
    # =========================================================================
    def business_rule_checks(self) -> List[ValidationFinding]:
        findings = []

        # Rule 1: Safety complaints MUST be P1
        complaints = self.db.scalars(select(Complaint)).all()
        safety_priority_violations = []
        for c in complaints:
            is_safety = c.category_code == "PRODUCT_SAFETY" or c.is_safety_incident
            if is_safety and c.priority != "P1":
                # Check if this was marked as an anomaly
                safety_priority_violations.append({
                    "complaint_id": c.complaint_id,
                    "priority": c.priority,
                    "category_code": c.category_code,
                    "is_anomaly": c.is_anomaly,
                })

        # Exclude intentional anomalies from hard validation fail, or warn if anomalies present
        unintentional = [v for v in safety_priority_violations if not v["is_anomaly"]]
        if unintentional:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="fail",
                message=f"Found {len(unintentional)} unflagged safety complaints not set to P1 (rule PR-001 violation)",
                table_name="complaints",
                details={"violations": unintentional[:10]},
            ))
        elif safety_priority_violations:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="warn",
                message=f"Found {len(safety_priority_violations)} deliberate anomaly safety complaints with P3/P4",
                table_name="complaints",
                details={"anomalies": safety_priority_violations},
            ))
        else:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="pass",
                message="All safety complaints strictly adhere to P1 priority per rule PR-001",
                table_name="complaints",
            ))

        # Rule 2: SLA deadlines match config policy
        sla_clocks = self.db.scalars(select(SLAClock)).all()
        sla_violations = []
        for s in sla_clocks:
            try:
                policy = self.sla_engine.get_policy(s.priority)
                if abs(s.resolution_hours - policy.resolution_hours) > 0.01:
                    sla_violations.append({
                        "sla_id": s.sla_id,
                        "priority": s.priority,
                        "clock_hours": s.resolution_hours,
                        "expected_hours": policy.resolution_hours,
                    })
            except Exception as ex:
                sla_violations.append({
                    "sla_id": s.sla_id,
                    "error": str(ex),
                })

        if sla_violations:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="sla_deadline_policy_alignment",
                status="fail",
                message=f"Found {len(sla_violations)} SLA clocks whose resolution_hours don't match policy config",
                table_name="sla_clocks",
                details={"violations": sla_violations[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="sla_deadline_policy_alignment",
                status="pass",
                message="All SLA clocks align with configured resolution time policies",
                table_name="sla_clocks",
            ))

        # Rule 3: Initial status event exists for complaints
        missing_initial_event = []
        for c in complaints:
            has_open_event = any(
                e.to_status == "open" for e in c.status_events
            )
            if not has_open_event:
                missing_initial_event.append({
                    "complaint_id": c.complaint_id,
                    "is_anomaly": c.is_anomaly,
                })

        unintentional_missing = [m for m in missing_initial_event if not m["is_anomaly"]]
        if unintentional_missing:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="complaint_initial_status_event",
                status="fail",
                message=f"Found {len(unintentional_missing)} complaints without initial 'open' status event",
                table_name="complaint_status_events",
                details={"violations": unintentional_missing[:10]},
            ))
        elif missing_initial_event:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="complaint_initial_status_event",
                status="warn",
                message=f"Found {len(missing_initial_event)} deliberate anomaly complaints without initial 'open' event",
                table_name="complaint_status_events",
                details={"anomalies": missing_initial_event},
            ))
        else:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="complaint_initial_status_event",
                status="pass",
                message="All complaints have an initial 'open' status event recorded",
                table_name="complaint_status_events",
            ))

        return findings

    # =========================================================================
    # 5. Integrity Checks
    # =========================================================================
    def integrity_checks(self) -> List[ValidationFinding]:
        findings = []

        # Orders: valid foreign keys
        orders = self.db.scalars(select(Order)).all()
        orphaned_orders = []
        for o in orders:
            if not self.db.get(Customer, o.customer_id_fk):
                orphaned_orders.append({"order_id": o.order_id, "missing_customer_fk": o.customer_id_fk})
            if not self.db.get(Product, o.product_id_fk):
                orphaned_orders.append({"order_id": o.order_id, "missing_product_fk": o.product_id_fk})

        if orphaned_orders:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="order_foreign_key_integrity",
                status="fail",
                message=f"Found {len(orphaned_orders)} orders referencing non-existent customer or product",
                table_name="orders",
                details={"violations": orphaned_orders[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="order_foreign_key_integrity",
                status="pass",
                message="All order foreign keys reference valid existing entities",
                table_name="orders",
            ))

        # Complaints: customer FK integrity
        complaints = self.db.scalars(select(Complaint)).all()
        orphaned_complaints = []
        for c in complaints:
            if c.customer_id_fk and not self.db.get(Customer, c.customer_id_fk):
                orphaned_complaints.append({
                    "complaint_id": c.complaint_id,
                    "missing_customer_fk": c.customer_id_fk,
                })
            if c.order_id_fk and not self.db.get(Order, c.order_id_fk):
                orphaned_complaints.append({
                    "complaint_id": c.complaint_id,
                    "missing_order_fk": c.order_id_fk,
                })

        if orphaned_complaints:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="complaint_foreign_key_integrity",
                status="fail",
                message=f"Found {len(orphaned_complaints)} complaints with orphaned customer or order references",
                table_name="complaints",
                details={"violations": orphaned_complaints[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="complaint_foreign_key_integrity",
                status="pass",
                message="All complaint foreign keys resolve to valid records",
                table_name="complaints",
            ))

        # Check for multiple current assignments for a single complaint
        assignment_violations = []
        for c in complaints:
            current_assignments = [a for a in c.assignments if a.is_current]
            if len(current_assignments) > 1:
                assignment_violations.append({
                    "complaint_id": c.complaint_id,
                    "current_assignment_count": len(current_assignments),
                    "assignment_ids": [a.assignment_id for a in current_assignments],
                })

        if assignment_violations:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="single_current_assignment",
                status="warn" if any(c.is_anomaly for c in complaints if c.complaint_id in [v["complaint_id"] for v in assignment_violations]) else "fail",
                message=f"Found {len(assignment_violations)} complaints with multiple active assignments",
                table_name="assignments",
                details={"violations": assignment_violations},
            ))
        else:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="single_current_assignment",
                status="pass",
                message="Each complaint has at most one current active assignment",
                table_name="assignments",
            ))

        return findings
