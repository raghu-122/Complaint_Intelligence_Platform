"""
Database loader — persists generated data dicts into SQLAlchemy ORM objects.
Handles all FK resolution (code -> int PK).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.team import Team
from app.models.agent import Agent
from app.models.category import Category
from app.models.priority_rule import PriorityRule
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.complaint import Complaint, ComplaintStatusEvent, ComplaintRelationship
from app.models.message import ComplaintMessage
from app.models.assignment import Assignment
from app.models.sla import SLAClock, SLAEvent
from app.models.resolution import Resolution
from app.models.survey import Survey


def _dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_all(db: Session, data: dict, clear_first: bool = False) -> dict[str, int]:
    """
    Load all generated data into the database.
    Returns record counts for each entity.
    """
    if clear_first:
        _clear_tables(db)

    counts: dict[str, int] = {}

    # Lookup maps: code/business_id -> DB id (int PK)
    team_map: dict[str, int] = {}
    agent_map: dict[str, int] = {}
    cat_map: dict[str, int] = {}
    product_map: dict[str, int] = {}
    customer_map: dict[str, int] = {}
    order_map: dict[str, int] = {}
    complaint_map: dict[str, int] = {}
    sla_clock_map: dict[str, int] = {}

    # 1. Categories
    for c in data.get("categories", []):
        obj = Category(
            code=c["code"],
            name=c["name"],
            description=c.get("description"),
            keywords=c["keywords"],
            safety_risk=c["safety_risk"],
            is_active=c["is_active"],
            config_version=c["config_version"],
            created_at=_dt(c.get("created_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        cat_map[c["code"]] = obj.id
    counts["categories"] = len(data.get("categories", []))

    # 2. Priority rules
    for r in data.get("priority_rules", []):
        obj = PriorityRule(
            rule_id=r["rule_id"],
            name=r["name"],
            description=r["description"],
            priority_code=r.get("priority_code"),
            priority_upgrade=r.get("priority_upgrade", 0),
            condition=r["condition"],
            precedence=r["precedence"],
            is_active=r["is_active"],
            config_version=r["config_version"],
            effective_date=r["effective_date"],
        )
        db.add(obj)
    db.flush()
    counts["priority_rules"] = len(data.get("priority_rules", []))

    # 3. Teams
    for t in data.get("teams", []):
        obj = Team(
            team_id=t["team_id"],
            code=t["code"],
            name=t["name"],
            description=t.get("description"),
            specializations=t["specializations"],
            handles_priority=t["handles_priority"],
            safety_capable=t["safety_capable"],
            is_active=t["is_active"],
            created_at=_dt(t.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_dt(t.get("created_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        team_map[t["code"]] = obj.id
    counts["teams"] = len(data.get("teams", []))

    # 4. Agents
    for a in data.get("agents", []):
        team_pk = team_map.get(a["team_id_fk_code"])
        obj = Agent(
            agent_id=a["agent_id"],
            team_id_fk=team_pk,
            name=a["name"],
            email=a["email"],
            role=a["role"],
            is_active=a["is_active"],
            max_concurrent_cases=a["max_concurrent_cases"],
            open_complaint_count=a["open_complaint_count"],
            created_at=_dt(a.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_dt(a.get("created_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        agent_map[a["agent_id"]] = obj.id
    counts["agents"] = len(data.get("agents", []))

    # 5. Products
    for p in data.get("products", []):
        obj = Product(
            product_id=p["product_id"],
            name=p["name"],
            description=p.get("description"),
            category=p["category"],
            subcategory=p.get("subcategory"),
            brand=p.get("brand"),
            sku=p["sku"],
            unit_price=Decimal(p["unit_price"]),
            currency=p["currency"],
            stock_quantity=p["stock_quantity"],
            is_active=p["is_active"],
            is_safety_flagged=p.get("is_safety_flagged", False),
            created_at=_dt(p.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_dt(p.get("updated_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        product_map[p["product_id"]] = obj.id
    counts["products"] = len(data.get("products", []))

    # 6. Customers
    for c in data.get("customers", []):
        obj = Customer(
            customer_id=c["customer_id"],
            first_name=c["first_name"],
            last_name=c["last_name"],
            email=c["email"],
            phone=c.get("phone"),
            address_line1=c.get("address_line1"),
            address_line2=c.get("address_line2"),
            city=c.get("city"),
            state=c.get("state"),
            postal_code=c.get("postal_code"),
            country=c.get("country", "US"),
            vulnerability_flag=c.get("vulnerability_flag", False),
            vulnerability_type=c.get("vulnerability_type"),
            is_active=c.get("is_active", True),
            account_tier=c.get("account_tier", "standard"),
            loyalty_points=c.get("loyalty_points", 0),
            is_synthetic=True,
            created_at=_dt(c.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_dt(c.get("updated_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        customer_map[c["customer_id"]] = obj.id
    counts["customers"] = len(data.get("customers", []))

    # 7. Orders
    for o in data.get("orders", []):
        customer_pk = customer_map.get(o["customer_id_fk_code"])
        product_pk = product_map.get(o["product_id_fk_code"])
        obj = Order(
            order_id=o["order_id"],
            customer_id_fk=customer_pk,
            product_id_fk=product_pk,
            quantity=o["quantity"],
            unit_price=Decimal(o["unit_price"]),
            discount_amount=Decimal(o["discount_amount"]),
            total_amount=Decimal(o["total_amount"]),
            currency=o["currency"],
            status=o["status"],
            shipping_address=o.get("shipping_address"),
            tracking_number=o.get("tracking_number"),
            ordered_at=_dt(o["ordered_at"]),
            shipped_at=_dt(o.get("shipped_at")),
            delivered_at=_dt(o.get("delivered_at")),
            created_at=_dt(o.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_dt(o.get("updated_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
        db.flush()
        order_map[o["order_id"]] = obj.id
    counts["orders"] = len(data.get("orders", []))

    # 7b. Order Items
    for oi in data.get("order_items", []):
        order_pk = order_map.get(oi["order_id_fk_code"])
        product_pk = product_map.get(oi["product_id_fk_code"])
        obj = OrderItem(
            order_item_id=oi["order_item_id"],
            order_id_fk=order_pk,
            product_id_fk=product_pk,
            quantity=oi["quantity"],
            unit_price=Decimal(oi["unit_price"]),
            discount_amount=Decimal(oi["discount_amount"]),
            line_total=Decimal(oi["line_total"]),
            created_at=_dt(oi.get("created_at")) or datetime.now(timezone.utc),
        )
        db.add(obj)
    db.flush()
    counts["order_items"] = len(data.get("order_items", []))

    # 8. Complaints
    for c in data.get("complaints", []):
        customer_pk = customer_map.get(c.get("customer_id_fk_code"))
        order_pk = order_map.get(c.get("order_id_fk_code"))
        prod_pk = product_map.get(c.get("product_id_fk_code"))
        cat_pk = cat_map.get(c.get("category_id_fk_code"))
        obj = Complaint(
            complaint_id=c["complaint_id"],
            customer_id_fk=customer_pk,
            order_id_fk=order_pk,
            product_id_fk=prod_pk,
            category_id_fk=cat_pk,
            subject=c["subject"],
            description=c["description"],
            channel=c["channel"],
            status=c["status"],
            priority=c["priority"],
            category_code=c.get("category_code"),
            classification_confidence=c.get("classification_confidence"),
            classification_evidence=c.get("classification_evidence"),
            classification_rule_id=c.get("classification_rule_id"),
            classification_rule_version=c.get("classification_rule_version"),
            priority_rule_applied=c.get("priority_rule_applied"),
            priority_explanation=c.get("priority_explanation"),
            sentiment=c.get("sentiment", "neutral"),
            sentiment_score=c.get("sentiment_score"),
            is_safety_incident=c.get("is_safety_incident", False),
            is_refund_pending=c.get("is_refund_pending", False),
            is_reopened=c.get("is_reopened", False),
            reopen_count=c.get("reopen_count", 0),
            is_escalated=c.get("is_escalated", False),
            escalation_reason=c.get("escalation_reason"),
            is_anomaly=c.get("is_anomaly", False),
            anomaly_id=c.get("anomaly_id"),
            anomaly_type=c.get("anomaly_type"),
            created_at=_dt(c["created_at"]),
            updated_at=_dt(c.get("updated_at")) or _dt(c["created_at"]),
            resolved_at=_dt(c.get("resolved_at")),
            closed_at=_dt(c.get("closed_at")),
        )
        db.add(obj)
        db.flush()
        complaint_map[c["complaint_id"]] = obj.id
    counts["complaints"] = len(data.get("complaints", []))

    # 9. Status events
    for e in data.get("status_events", []):
        comp_pk = complaint_map.get(e["complaint_id_fk_code"])
        if comp_pk:
            db.add(ComplaintStatusEvent(
                complaint_id_fk=comp_pk,
                from_status=e.get("from_status"),
                to_status=e["to_status"],
                changed_by=e.get("changed_by"),
                reason=e.get("reason"),
                occurred_at=_dt(e["occurred_at"]),
            ))
    db.flush()

    # 10. Complaint relationships
    for rel in data.get("complaint_relationships", []):
        primary_pk = complaint_map.get(rel["primary_complaint_id_fk_code"])
        related_pk = complaint_map.get(rel["related_complaint_id_fk_code"])
        if primary_pk and related_pk:
            db.add(ComplaintRelationship(
                primary_complaint_id_fk=primary_pk,
                related_complaint_id_fk=related_pk,
                relationship_type=rel["relationship_type"],
                notes=rel.get("notes"),
                created_at=_dt(rel.get("created_at")) or datetime.now(timezone.utc),
            ))
    db.flush()

    # 11. Assignments
    for a in data.get("assignments", []):
        comp_pk = complaint_map.get(a["complaint_id_fk_code"])
        team_pk = team_map.get(a.get("team_id_fk_code"))
        agent_pk = agent_map.get(a.get("agent_id_fk_code"))
        if comp_pk:
            db.add(Assignment(
                assignment_id=a["assignment_id"],
                complaint_id_fk=comp_pk,
                team_id_fk=team_pk,
                agent_id_fk=agent_pk,
                assignment_type=a.get("assignment_type", "initial"),
                assigned_by=a.get("assigned_by"),
                reason=a.get("reason"),
                rule_applied=a.get("rule_applied"),
                is_current=a.get("is_current", True),
                assigned_at=_dt(a["assigned_at"]),
            ))
    db.flush()
    counts["assignments"] = len(data.get("assignments", []))

    # 12. SLA clocks
    for s in data.get("sla_clocks", []):
        comp_pk = complaint_map.get(s["complaint_id_fk_code"])
        if comp_pk:
            obj = SLAClock(
                sla_id=s["sla_id"],
                complaint_id_fk=comp_pk,
                priority=s["priority"],
                resolution_hours=s["resolution_hours"],
                first_response_hours=s["first_response_hours"],
                escalation_hours=s["escalation_hours"],
                start_time=_dt(s["start_time"]),
                original_deadline=_dt(s["original_deadline"]),
                current_deadline=_dt(s["current_deadline"]),
                first_response_deadline=_dt(s["first_response_deadline"]),
                escalation_threshold_time=_dt(s["escalation_threshold_time"]),
                accumulated_paused_hours=s.get("accumulated_paused_hours", 0.0),
                status=s.get("status", "running"),
                is_breached=s.get("is_breached", False),
                breached_at=_dt(s.get("breached_at")),
                is_escalated=s.get("is_escalated", False),
                is_anomaly=s.get("is_anomaly", False),
                anomaly_id=s.get("anomaly_id"),
                config_version=s.get("config_version", "1.0.0"),
                created_at=_dt(s.get("created_at")) or datetime.now(timezone.utc),
                updated_at=_dt(s.get("created_at")) or datetime.now(timezone.utc),
            )
            db.add(obj)
            db.flush()
            sla_clock_map[s["sla_id"]] = obj.id
    counts["sla_clocks"] = len(data.get("sla_clocks", []))

    # 13. SLA events
    for e in data.get("sla_events", []):
        sla_pk = sla_clock_map.get(e["sla_id_fk_code"])
        if sla_pk:
            db.add(SLAEvent(
                sla_id_fk=sla_pk,
                event_type=e["event_type"],
                reason=e.get("reason"),
                hours_paused=e.get("hours_paused"),
                occurred_at=_dt(e["occurred_at"]),
                is_anomaly=e.get("is_anomaly", False),
                anomaly_id=e.get("anomaly_id"),
            ))
    db.flush()

    # 14. Messages
    for m in data.get("messages", []):
        comp_pk = complaint_map.get(m["complaint_id_fk_code"])
        if comp_pk:
            db.add(ComplaintMessage(
                message_id=m["message_id"],
                complaint_id_fk=comp_pk,
                message_type=m.get("message_type", "customer_message"),
                sender_type=m["sender_type"],
                sender_id=m.get("sender_id"),
                sender_name=m.get("sender_name"),
                body=m["body"],
                is_customer_visible=m.get("is_customer_visible", True),
                channel=m.get("channel"),
                delivery_status=m.get("delivery_status"),
                sequence_number=m["sequence_number"],
                sent_at=_dt(m["sent_at"]),
                created_at=_dt(m.get("created_at")) or datetime.now(timezone.utc),
                is_anomaly=m.get("is_anomaly", False),
                anomaly_id=m.get("anomaly_id"),
            ))
    db.flush()
    counts["messages"] = len(data.get("messages", []))

    # 15. Resolutions
    for r in data.get("resolutions", []):
        comp_pk = complaint_map.get(r["complaint_id_fk_code"])
        if comp_pk:
            db.add(Resolution(
                resolution_id=r["resolution_id"],
                complaint_id_fk=comp_pk,
                resolution_type=r["resolution_type"],
                description=r["description"],
                refund_amount=Decimal(r["refund_amount"]) if r.get("refund_amount") else None,
                refund_currency=r.get("refund_currency"),
                refund_approved=r.get("refund_approved"),
                refund_processed_at=_dt(r.get("refund_processed_at")),
                resolved_by_agent_id=r.get("resolved_by_agent_id"),
                resolved_by_team_id=r.get("resolved_by_team_id"),
                is_superseded=r.get("is_superseded", False),
                superseded_by_resolution_id=r.get("superseded_by_resolution_id"),
                resolved_at=_dt(r["resolved_at"]),
                created_at=_dt(r.get("created_at")) or datetime.now(timezone.utc),
            ))
    db.flush()
    counts["resolutions"] = len(data.get("resolutions", []))

    # 16. Surveys
    for s in data.get("surveys", []):
        comp_pk = complaint_map.get(s["complaint_id_fk_code"])
        if comp_pk:
            db.add(Survey(
                survey_id=s["survey_id"],
                complaint_id_fk=comp_pk,
                rating=s["rating"],
                feedback=s.get("feedback"),
                submitted_by=s.get("submitted_by"),
                submitted_before_closure=s.get("submitted_before_closure", False),
                is_anomaly=s.get("is_anomaly", False),
                anomaly_id=s.get("anomaly_id"),
                submitted_at=_dt(s["submitted_at"]),
                created_at=_dt(s.get("created_at")) or datetime.now(timezone.utc),
            ))
    db.flush()
    counts["surveys"] = len(data.get("surveys", []))

    db.commit()
    return counts


def _clear_tables(db: Session) -> None:
    """Clear all data tables in reverse dependency order."""
    from sqlalchemy import text
    tables = [
        "surveys", "resolutions", "sla_events", "sla_clocks",
        "assignments", "complaint_relationships", "complaint_messages",
        "complaint_status_events", "complaints", "order_items", "orders",
        "customers", "products", "agents", "teams",
        "priority_rules", "categories",
    ]
    is_sqlite = False
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "sqlite":
            is_sqlite = True
    except Exception:
        pass

    if is_sqlite:
        db.execute(text("PRAGMA foreign_keys=OFF"))
    for table in tables:
        db.execute(text(f"DELETE FROM {table}"))
    if is_sqlite:
        db.execute(text("PRAGMA foreign_keys=ON"))
    db.commit()
