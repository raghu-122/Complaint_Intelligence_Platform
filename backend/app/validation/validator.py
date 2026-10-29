"""
Validation Engine — comprehensive data quality and rule validation.

Implements:
1. schema_checks: required fields, types, and constraints
2. chronology_checks: timeline ordering across events and lifecycles
3. arithmetic_checks: numeric integrity (order totals, paused hours)
4. business_rule_checks: business policy enforcement (safety P1, SLA configs)
5. integrity_checks: referential integrity, orphaned records, unique constraints

Performance: all checks use set-based SQL queries to avoid N+1 query patterns
and ensure the endpoint responds within the 15-second timeout on the full dataset.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, func, and_, text, exists, literal
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
    """Runs data quality, integrity, and business logic checks against the database.
    
    All checks use efficient SQL queries rather than per-row Python loops
    to avoid N+1 patterns and stay within API response time limits.
    """

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

        # Complaints: required core fields — single query
        invalid_complaint_ids = self.db.scalars(
            select(Complaint.complaint_id).where(
                (Complaint.complaint_id.is_(None)) |
                (Complaint.subject.is_(None)) |
                (Complaint.description.is_(None)) |
                (Complaint.status.is_(None)) |
                (Complaint.priority.is_(None))
            )
        ).all()

        if invalid_complaint_ids:
            findings.append(ValidationFinding(
                category="schema",
                check_name="complaint_required_fields",
                status="fail",
                message=f"Found {len(invalid_complaint_ids)} complaints with missing required fields",
                table_name="complaints",
                details={"invalid_ids": list(invalid_complaint_ids[:10])},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="complaint_required_fields",
                status="pass",
                message="All complaints have valid required fields",
                table_name="complaints",
            ))

        # Customers: valid email & name — single query
        invalid_customer_ids = self.db.scalars(
            select(Customer.customer_id).where(
                (Customer.customer_id.is_(None)) |
                (Customer.first_name.is_(None)) |
                (Customer.last_name.is_(None)) |
                (Customer.email.is_(None)) |
                (~Customer.email.contains("@"))
            )
        ).all()

        if invalid_customer_ids:
            findings.append(ValidationFinding(
                category="schema",
                check_name="customer_required_fields",
                status="fail",
                message=f"Found {len(invalid_customer_ids)} customers with invalid name or email format",
                table_name="customers",
                details={"invalid_ids": list(invalid_customer_ids[:10])},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="customer_required_fields",
                status="pass",
                message="All customers have valid names and emails",
                table_name="customers",
            ))

        # Products: unit_price non-negative & non-empty SKU — single query
        invalid_product_ids = self.db.scalars(
            select(Product.product_id).where(
                (Product.sku.is_(None)) |
                (Product.sku == "") |
                (Product.unit_price < 0)
            )
        ).all()

        if invalid_product_ids:
            findings.append(ValidationFinding(
                category="schema",
                check_name="product_constraints",
                status="fail",
                message=f"Found {len(invalid_product_ids)} products with negative price or empty SKU",
                table_name="products",
                details={"invalid_ids": list(invalid_product_ids[:10])},
            ))
        else:
            findings.append(ValidationFinding(
                category="schema",
                check_name="product_constraints",
                status="pass",
                message="All products satisfy pricing and SKU constraints",
                table_name="products",
            ))

        # Teams: valid JSON specializations — fetch only teams (small table)
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

        # Complaints: created_at <= resolved_at <= closed_at — SQL filter
        chrono_rows = self.db.execute(
            select(
                Complaint.complaint_id,
                Complaint.created_at,
                Complaint.resolved_at,
                Complaint.closed_at,
            ).where(
                # resolved_at before created_at
                (
                    (Complaint.resolved_at.isnot(None)) &
                    (Complaint.resolved_at < Complaint.created_at)
                ) |
                # closed_at before resolved_at
                (
                    (Complaint.closed_at.isnot(None)) &
                    (Complaint.resolved_at.isnot(None)) &
                    (Complaint.closed_at < Complaint.resolved_at)
                ) |
                # closed_at before created_at
                (
                    (Complaint.closed_at.isnot(None)) &
                    (Complaint.closed_at < Complaint.created_at)
                )
            )
        ).all()

        chrono_violations = [
            {
                "complaint_id": row.complaint_id,
                "reason": (
                    f"created_at ({row.created_at}) > resolved_at ({row.resolved_at})"
                    if row.resolved_at and row.resolved_at < row.created_at
                    else f"resolved_at ({row.resolved_at}) > closed_at ({row.closed_at})"
                    if row.closed_at and row.resolved_at and row.closed_at < row.resolved_at
                    else f"created_at ({row.created_at}) > closed_at ({row.closed_at})"
                )
            }
            for row in chrono_rows
        ]

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

        # Surveys: submitted_at should be >= closed_at — SQL filter
        # Join surveys with complaints to compare timestamps
        survey_violation_rows = self.db.execute(
            select(
                Survey.survey_id,
                Survey.submitted_at,
                Survey.is_anomaly,
                Survey.submitted_before_closure,
                Complaint.complaint_id,
                Complaint.status,
                Complaint.closed_at,
            )
            .join(Complaint, Survey.complaint_id_fk == Complaint.id)
            .where(
                (Survey.is_anomaly == False) &
                (Survey.submitted_before_closure == False) &
                (
                    # Survey on open complaint (no closed_at)
                    (
                        Complaint.closed_at.is_(None) &
                        (Complaint.status != "closed")
                    ) |
                    # Survey before closure timestamp
                    (
                        Complaint.closed_at.isnot(None) &
                        (Survey.submitted_at < Complaint.closed_at)
                    )
                )
            )
        ).all()

        survey_violations = [
            {
                "survey_id": row.survey_id,
                "complaint_id": row.complaint_id,
                "reason": (
                    f"Survey submitted_at ({row.submitted_at}) < closed_at ({row.closed_at})"
                    if row.closed_at
                    else "Survey submitted for unclosed complaint without anomaly flag"
                ),
            }
            for row in survey_violation_rows
        ]

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

        # Orders: ordered_at <= shipped_at <= delivered_at — SQL filter
        order_violation_rows = self.db.execute(
            select(
                Order.order_id,
                Order.ordered_at,
                Order.shipped_at,
                Order.delivered_at,
            ).where(
                (
                    Order.shipped_at.isnot(None) &
                    (Order.shipped_at < Order.ordered_at)
                ) |
                (
                    Order.delivered_at.isnot(None) &
                    Order.shipped_at.isnot(None) &
                    (Order.delivered_at < Order.shipped_at)
                )
            )
        ).all()

        order_violations = [
            {
                "order_id": row.order_id,
                "reason": (
                    f"ordered_at ({row.ordered_at}) > shipped_at ({row.shipped_at})"
                    if row.shipped_at and row.shipped_at < row.ordered_at
                    else f"shipped_at ({row.shipped_at}) > delivered_at ({row.delivered_at})"
                ),
            }
            for row in order_violation_rows
        ]

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

        # Order totals: use SQL aggregation on order_items when available
        # Fetch order_items grouped by order FK and compare with orders.total_amount
        from app.models.order_item import OrderItem

        # Get all orders with their item sums in one query
        item_sums = dict(
            self.db.execute(
                select(
                    OrderItem.order_id_fk,
                    func.sum(OrderItem.line_total).label("item_total"),
                ).group_by(OrderItem.order_id_fk)
            ).all()
        )

        orders = self.db.execute(
            select(
                Order.id,
                Order.order_id,
                Order.total_amount,
                Order.unit_price,
                Order.quantity,
                Order.discount_amount,
            )
        ).all()

        math_violations = []
        for row in orders:
            if row.id in item_sums:
                expected = Decimal(str(item_sums[row.id]))
            else:
                unit = Decimal(str(row.unit_price)) if row.unit_price is not None else Decimal("0")
                disc = Decimal(str(row.discount_amount or "0"))
                qty = int(row.quantity) if row.quantity else 1
                expected = unit * qty - disc

            actual = Decimal(str(row.total_amount)) if row.total_amount is not None else Decimal("0")
            if abs(actual - expected) >= Decimal("0.02"):
                math_violations.append({
                    "order_id": row.order_id,
                    "expected": str(expected.quantize(Decimal("0.01"))),
                    "actual": str(actual),
                    "difference": str((actual - expected).quantize(Decimal("0.01"))),
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

        # Non-negative SLA accumulated pause — SQL query
        invalid_pause_count = self.db.scalar(
            select(func.count(SLAClock.id)).where(
                (SLAClock.accumulated_paused_hours.isnot(None)) &
                (SLAClock.accumulated_paused_hours < 0)
            )
        ) or 0

        if invalid_pause_count > 0:
            invalid_pauses = self.db.scalars(
                select(SLAClock.sla_id).where(
                    (SLAClock.accumulated_paused_hours.isnot(None)) &
                    (SLAClock.accumulated_paused_hours < 0)
                ).limit(20)
            ).all()
            findings.append(ValidationFinding(
                category="arithmetic",
                check_name="sla_paused_hours_non_negative",
                status="fail",
                message=f"Found {invalid_pause_count} SLA clocks with negative paused hours",
                table_name="sla_clocks",
                details={"invalid_ids": list(invalid_pauses)},
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

        # Rule 1: Safety complaints MUST be P1 — SQL query
        safety_violations = self.db.execute(
            select(
                Complaint.complaint_id,
                Complaint.priority,
                Complaint.category_code,
                Complaint.is_anomaly,
            ).where(
                (
                    (Complaint.category_code == "PRODUCT_SAFETY") |
                    (Complaint.is_safety_incident == True)
                ) &
                (Complaint.priority != "P1")
            )
        ).all()

        unintentional = [
            {"complaint_id": r.complaint_id, "priority": r.priority,
             "category_code": r.category_code, "is_anomaly": r.is_anomaly}
            for r in safety_violations if not r.is_anomaly
        ]
        intentional = [
            {"complaint_id": r.complaint_id, "priority": r.priority,
             "category_code": r.category_code, "is_anomaly": r.is_anomaly}
            for r in safety_violations if r.is_anomaly
        ]

        if unintentional:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="fail",
                message=f"Found {len(unintentional)} unflagged safety complaints not set to P1 (rule PR-001 violation)",
                table_name="complaints",
                details={"violations": unintentional[:10]},
            ))
        elif intentional:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="warn",
                message=f"Found {len(intentional)} deliberate anomaly safety complaints with P3/P4",
                table_name="complaints",
                details={"anomalies": intentional[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="safety_complaints_must_be_p1",
                status="pass",
                message="All safety complaints strictly adhere to P1 priority per rule PR-001",
                table_name="complaints",
            ))

        # Rule 2: SLA deadlines match config policy — fetch all sla_clocks (targeted columns only)
        sla_rows = self.db.execute(
            select(SLAClock.sla_id, SLAClock.priority, SLAClock.resolution_hours)
        ).all()
        sla_violations = []
        for row in sla_rows:
            try:
                policy = self.sla_engine.get_policy(row.priority)
                if abs(row.resolution_hours - policy.resolution_hours) > 0.01:
                    sla_violations.append({
                        "sla_id": row.sla_id,
                        "priority": row.priority,
                        "clock_hours": row.resolution_hours,
                        "expected_hours": policy.resolution_hours,
                    })
            except Exception as ex:
                sla_violations.append({"sla_id": row.sla_id, "error": str(ex)})

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

        # Rule 3: Initial status event exists for complaints — use SQL subquery
        # Find complaint IDs that have NO 'open' status event
        has_open_event_subq = (
            select(ComplaintStatusEvent.complaint_id_fk)
            .where(ComplaintStatusEvent.to_status == "open")
            .scalar_subquery()
        )
        missing_event_rows = self.db.execute(
            select(Complaint.complaint_id, Complaint.is_anomaly).where(
                Complaint.id.not_in(
                    select(ComplaintStatusEvent.complaint_id_fk).where(
                        ComplaintStatusEvent.to_status == "open"
                    )
                )
            )
        ).all()

        unintentional_missing = [
            {"complaint_id": r.complaint_id, "is_anomaly": r.is_anomaly}
            for r in missing_event_rows if not r.is_anomaly
        ]
        intentional_missing = [
            {"complaint_id": r.complaint_id, "is_anomaly": r.is_anomaly}
            for r in missing_event_rows if r.is_anomaly
        ]

        if unintentional_missing:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="complaint_initial_status_event",
                status="fail",
                message=f"Found {len(unintentional_missing)} complaints without initial 'open' status event",
                table_name="complaint_status_events",
                details={"violations": unintentional_missing[:10]},
            ))
        elif intentional_missing:
            findings.append(ValidationFinding(
                category="business_rules",
                check_name="complaint_initial_status_event",
                status="warn",
                message=f"Found {len(intentional_missing)} deliberate anomaly complaints without initial 'open' event",
                table_name="complaint_status_events",
                details={"anomalies": intentional_missing[:10]},
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

        # Pre-load valid customer and product IDs as sets for O(1) lookup
        valid_customer_ids: set = set(
            self.db.scalars(select(Customer.id)).all()
        )
        valid_product_ids: set = set(
            self.db.scalars(select(Product.id)).all()
        )
        valid_order_ids: set = set(
            self.db.scalars(select(Order.id)).all()
        )

        # Orders: valid foreign keys — SQL LEFT JOIN approach
        orphaned_orders = self.db.execute(
            select(Order.order_id, Order.customer_id_fk, Order.product_id_fk).where(
                ~Order.customer_id_fk.in_(
                    select(Customer.id)
                ) |
                ~Order.product_id_fk.in_(
                    select(Product.id)
                )
            )
        ).all()

        orphaned_order_list = [
            {"order_id": row.order_id,
             "missing_customer_fk": row.customer_id_fk if row.customer_id_fk not in valid_customer_ids else None,
             "missing_product_fk": row.product_id_fk if row.product_id_fk not in valid_product_ids else None}
            for row in orphaned_orders
        ]

        if orphaned_order_list:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="order_foreign_key_integrity",
                status="fail",
                message=f"Found {len(orphaned_order_list)} orders referencing non-existent customer or product",
                table_name="orders",
                details={"violations": orphaned_order_list[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="order_foreign_key_integrity",
                status="pass",
                message="All order foreign keys reference valid existing entities",
                table_name="orders",
            ))

        # Complaints: customer and order FK integrity — SQL query (nulls are OK for anomaly testing)
        orphaned_complaint_rows = self.db.execute(
            select(Complaint.complaint_id, Complaint.customer_id_fk, Complaint.order_id_fk).where(
                # customer_id_fk non-null but references missing customer
                (
                    Complaint.customer_id_fk.isnot(None) &
                    ~Complaint.customer_id_fk.in_(select(Customer.id))
                ) |
                # order_id_fk non-null but references missing order
                (
                    Complaint.order_id_fk.isnot(None) &
                    ~Complaint.order_id_fk.in_(select(Order.id))
                )
            )
        ).all()

        orphaned_complaint_list = [
            {
                "complaint_id": row.complaint_id,
                "missing_customer_fk": row.customer_id_fk if (row.customer_id_fk and row.customer_id_fk not in valid_customer_ids) else None,
                "missing_order_fk": row.order_id_fk if (row.order_id_fk and row.order_id_fk not in valid_order_ids) else None,
            }
            for row in orphaned_complaint_rows
        ]

        if orphaned_complaint_list:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="complaint_foreign_key_integrity",
                status="fail",
                message=f"Found {len(orphaned_complaint_list)} complaints with orphaned customer or order references",
                table_name="complaints",
                details={"violations": orphaned_complaint_list[:10]},
            ))
        else:
            findings.append(ValidationFinding(
                category="integrity",
                check_name="complaint_foreign_key_integrity",
                status="pass",
                message="All complaint foreign keys resolve to valid records",
                table_name="complaints",
            ))

        # Multiple current assignments — SQL GROUP BY
        multi_assign_rows = self.db.execute(
            select(
                Assignment.complaint_id_fk,
                func.count(Assignment.id).label("cnt"),
            )
            .where(Assignment.is_current == True)
            .group_by(Assignment.complaint_id_fk)
            .having(func.count(Assignment.id) > 1)
        ).all()

        if multi_assign_rows:
            # Fetch complaint_ids and anomaly flags for context
            comp_fks = [r.complaint_id_fk for r in multi_assign_rows]
            comp_anomaly_map = dict(
                self.db.execute(
                    select(Complaint.id, Complaint.complaint_id, Complaint.is_anomaly).where(
                        Complaint.id.in_(comp_fks)
                    )
                ).all()
            )
            assignment_violations = [
                {
                    "complaint_fk": row.complaint_id_fk,
                    "current_assignment_count": row.cnt,
                }
                for row in multi_assign_rows
            ]
            # Determine status: warn if anomalies are involved, fail otherwise
            any_anomaly = any(
                comp_anomaly_map.get(r.complaint_id_fk, (None, None, False))[2]
                for r in multi_assign_rows
            )
            findings.append(ValidationFinding(
                category="integrity",
                check_name="single_current_assignment",
                status="warn" if any_anomaly else "fail",
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
