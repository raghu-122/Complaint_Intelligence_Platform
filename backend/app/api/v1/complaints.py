"""
Complaints API router.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.complaint import Complaint, ComplaintRelationship, ComplaintStatusEvent
from app.models.message import ComplaintMessage
from app.models.customer import Customer
from app.models.order import Order
from app.models.category import Category
from app.models.team import Team
from app.models.agent import Agent
from app.models.assignment import Assignment
from app.models.sla import SLAClock
from app.models.resolution import Resolution
from app.models.survey import Survey
from app.engine import get_classifier, get_priority_engine, get_assignment_engine, get_sla_engine
from app.schemas.complaint import (
    ComplaintDetail,
    ComplaintListItem,
    ComplaintRelationshipSchema,
    ComplaintCreateRequest,
    ComplaintMessageCreateRequest,
    ComplaintMessageSchema,
    ComplaintUpdateRequest,
    ComplaintResolutionCreateRequest,
    ComplaintSurveyCreateRequest,
    ResolutionSchema,
    SurveySchema,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/complaints", tags=["Complaints"])


def _to_list_item(c: Complaint) -> ComplaintListItem:
    assigned_team = None
    assigned_agent = None
    for a in c.assignments:
        if a.is_current:
            assigned_team = a.team.code if a.team else None
            assigned_agent = a.agent.name if a.agent else None
            break

    return ComplaintListItem(
        id=c.id,
        complaint_id=c.complaint_id,
        customer_id=c.customer.customer_id if c.customer else None,
        customer_name=c.customer.full_name if c.customer else None,
        order_id=c.order.order_id if c.order else None,
        category_code=c.category_code,
        category_name=c.category.name if c.category else None,
        subject=c.subject,
        description=c.description,
        channel=c.channel,
        status=c.status,
        priority=c.priority,
        sentiment=c.sentiment,
        sentiment_score=c.sentiment_score,
        is_safety_incident=c.is_safety_incident,
        is_refund_pending=c.is_refund_pending,
        is_reopened=c.is_reopened,
        reopen_count=c.reopen_count,
        is_escalated=c.is_escalated,
        is_anomaly=c.is_anomaly,
        created_at=c.created_at,
        updated_at=c.updated_at,
        resolved_at=c.resolved_at,
        closed_at=c.closed_at,
        assigned_team=assigned_team,
        assigned_agent=assigned_agent,
        sla_status=c.sla_clock.status if c.sla_clock else None,
        sla_breached=c.sla_clock.is_breached if c.sla_clock else None,
    )


@router.get("", response_model=PaginatedResponse[ComplaintListItem])
def list_complaints(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    category_code: Optional[str] = Query(default=None),
    is_safety_incident: Optional[bool] = Query(default=None),
    safety_only: Optional[bool] = Query(default=None),
    is_escalated: Optional[bool] = Query(default=None),
    customer_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List complaints with filtering and pagination."""
    query = select(Complaint).options(
        selectinload(Complaint.customer),
        selectinload(Complaint.order),
        selectinload(Complaint.category),
        selectinload(Complaint.assignments).selectinload(Assignment.team),
        selectinload(Complaint.assignments).selectinload(Assignment.agent),
        selectinload(Complaint.sla_clock),
    )

    if status:
        query = query.where(Complaint.status == status)
    if priority:
        query = query.where(Complaint.priority == priority)
    if channel:
        query = query.where(Complaint.channel == channel)
    if category_code:
        query = query.where(Complaint.category_code == category_code)
    if is_safety_incident is not None:
        query = query.where(Complaint.is_safety_incident == is_safety_incident)
    elif safety_only is not None:
        query = query.where(Complaint.is_safety_incident == safety_only)
    if is_escalated is not None:
        query = query.where(Complaint.is_escalated == is_escalated)
    if customer_id:
        from app.models.customer import Customer
        query = query.join(Complaint.customer).where(Customer.customer_id == customer_id)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Complaint.complaint_id.ilike(search_filter),
                Complaint.subject.ilike(search_filter),
                Complaint.description.ilike(search_filter),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sort descending by creation date
    query = query.order_by(desc(Complaint.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    complaints = db.scalars(query).all()
    items = [_to_list_item(c) for c in complaints]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
):
    """Get single complaint by business ID (e.g. CMP-2026-000001) or numeric ID."""
    query = select(Complaint).options(
        selectinload(Complaint.customer),
        selectinload(Complaint.order),
        selectinload(Complaint.category),
        selectinload(Complaint.status_events),
        selectinload(Complaint.messages),
        selectinload(Complaint.assignments).selectinload(Assignment.team),
        selectinload(Complaint.assignments).selectinload(Assignment.agent),
        selectinload(Complaint.sla_clock),
        selectinload(Complaint.resolutions),
        selectinload(Complaint.surveys),
    )

    if complaint_id.isdigit():
        c = db.scalar(query.where(Complaint.id == int(complaint_id)))
    else:
        c = db.scalar(query.where(Complaint.complaint_id == complaint_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    base = _to_list_item(c)

    # Format assignments
    assignments_list = []
    current_asn = None
    for a in c.assignments:
        assignments_list.append({
            "id": a.id,
            "assignment_id": a.assignment_id,
            "team_code": a.team.code if a.team else None,
            "team_name": a.team.name if a.team else None,
            "agent_id": a.agent.agent_id if a.agent else None,
            "agent_name": a.agent.name if a.agent else None,
            "assignment_type": a.assignment_type,
            "assigned_by": a.assigned_by,
            "reason": a.reason,
            "rule_applied": a.rule_applied,
            "is_current": a.is_current,
            "assigned_at": a.assigned_at,
        })
        if a.is_current and not current_asn:
            current_asn = {
                "agent_name": a.agent.name if a.agent else (a.assigned_by or "System"),
                "team_name": a.team.name if a.team else (a.team.code if a.team else "General Support"),
                "assigned_at": a.assigned_at,
            }

    # Format customer summary for UI card
    cust_data = None
    if c.customer:
        cust_data = {
            "customer_id": c.customer.customer_id,
            "name": c.customer.full_name or f"{c.customer.first_name} {c.customer.last_name}".strip(),
            "email": c.customer.email,
            "account_tier": c.customer.account_tier,
            "vulnerability_flag": c.customer.vulnerability_flag,
        }

    # Format order summary for UI card
    order_data = None
    if c.order:
        order_data = {
            "order_id": c.order.order_id,
            "total_amount": str(c.order.total_amount),
            "status": c.order.status,
            "ordered_at": c.order.ordered_at,
        }

    # Relationships
    rel_query = select(ComplaintRelationship).where(
        or_(
            ComplaintRelationship.primary_complaint_id_fk == c.id,
            ComplaintRelationship.related_complaint_id_fk == c.id,
        )
    )
    relationships = db.scalars(rel_query).all()
    rels_list = []
    for r in relationships:
        primary = db.get(Complaint, r.primary_complaint_id_fk)
        related = db.get(Complaint, r.related_complaint_id_fk)
        if primary and related:
            rels_list.append(ComplaintRelationshipSchema(
                id=r.id,
                primary_complaint_id=primary.complaint_id,
                related_complaint_id=related.complaint_id,
                relationship_type=r.relationship_type,
                notes=r.notes,
                created_at=r.created_at,
            ))

    return ComplaintDetail(
        **base.model_dump(),
        classification_confidence=c.classification_confidence,
        classification_evidence=c.classification_evidence,
        classification_rule_id=c.classification_rule_id,
        classification_rule_version=c.classification_rule_version,
        priority_rule_applied=c.priority_rule_applied,
        priority_explanation=c.priority_explanation,
        anomaly_id=c.anomaly_id,
        anomaly_type=c.anomaly_type,
        customer=cust_data,
        order=order_data,
        current_assignment=current_asn,
        status_events=c.status_events,
        messages=c.messages,
        assignments=assignments_list,
        sla_clock=c.sla_clock,
        resolutions=c.resolutions,
        surveys=c.surveys,
        related_complaints=rels_list,
    )


@router.post("", response_model=ComplaintListItem, status_code=status.HTTP_201_CREATED)
def create_complaint(
    req: ComplaintCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new complaint with automated triage, classification, SLA clock, and routing."""
    customer = db.get(Customer, req.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer ID {req.customer_id} not found",
        )

    order = db.get(Order, req.order_id) if req.order_id else None
    subject = req.subject or req.title or "Customer Support Ticket"

    # Automated keyword classification
    clf = get_classifier()
    clf_res = clf.classify(text=req.description, subject=subject)

    # Determine safety incident status
    is_safety = req.is_safety_incident if req.is_safety_incident is not None else (clf_res.category_code == "PRODUCT_SAFETY")

    # Priority determination engine (PR-001 through PR-005)
    pri_eng = get_priority_engine()
    sentiment_label, sentiment_score = pri_eng.detect_sentiment(req.description)
    prior_comps = db.scalar(
        select(func.count(Complaint.id)).where(Complaint.customer_id_fk == req.customer_id)
    ) or 0

    pri_decision = pri_eng.calculate_priority(
        category_code=clf_res.category_code,
        is_safety_category=is_safety,
        sentiment=sentiment_label,
        order_total=order.total_amount if order else None,
        customer_vulnerability_flag=customer.vulnerability_flag or False,
        prior_complaint_count=prior_comps,
    )

    # Generate sequential business ID
    max_id = db.scalar(select(func.max(Complaint.id))) or 0
    new_cid = f"CMP-2026-{(max_id + 1):06d}"
    now_utc = datetime.now(timezone.utc)

    # Resolve category model
    category = db.scalar(select(Category).where(Category.code == clf_res.category_code))

    complaint = Complaint(
        complaint_id=new_cid,
        customer_id_fk=customer.id,
        order_id_fk=order.id if order else None,
        category_code=category.code if category else clf_res.category_code,
        subject=subject,
        description=req.description,
        channel=req.channel,
        status="open",
        priority=pri_decision.priority,
        sentiment=sentiment_label,
        sentiment_score=sentiment_score,
        is_safety_incident=is_safety,
        classification_confidence=clf_res.confidence,
        classification_evidence=clf_res.evidence,
        classification_rule_id=clf_res.rule_id,
        classification_rule_version=clf_res.rule_version,
        priority_rule_applied=pri_decision.rule_applied,
        priority_explanation=pri_decision.explanation,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(complaint)
    db.flush()

    # Initial open status event
    db.add(ComplaintStatusEvent(
        complaint_id_fk=complaint.id,
        from_status=None,
        to_status="open",
        reason="Initial complaint registration",
        changed_by="customer",
        occurred_at=now_utc,
    ))

    # Agent routing and assignment
    asg_eng = get_assignment_engine()
    team_dict = asg_eng.get_team_for_category(complaint.category_code, is_safety=complaint.is_safety_incident)
    team_code = team_dict["code"] if team_dict else "GENERAL"
    team = db.scalar(select(Team).where(Team.code == team_code))

    agent = None
    if team:
        agent = db.scalar(
            select(Agent)
            .where(Agent.team_id_fk == team.id, Agent.is_active == True)
            .order_by(Agent.open_complaint_count.asc(), Agent.id.asc())
        )
        if agent:
            agent.open_complaint_count += 1

    assignment = Assignment(
        assignment_id=f"ASN-{new_cid}-01",
        complaint_id_fk=complaint.id,
        team_id_fk=team.id if team else None,
        agent_id_fk=agent.id if agent else None,
        assignment_type="initial",
        assigned_by="system_auto_router",
        reason=f"Auto-routed to {team.name if team else 'General Support'}",
        rule_applied="ROUTING_RULE_V1",
        is_current=True,
        assigned_at=now_utc,
    )
    db.add(assignment)

    # SLA Clock initialization
    sla_eng = get_sla_engine()
    policy = sla_eng.get_policy(complaint.priority)
    deadline = sla_eng.calculate_deadline(now_utc, complaint.priority)
    first_resp_dl = sla_eng.calculate_first_response_deadline(now_utc, complaint.priority)
    esc_thresh = sla_eng.calculate_escalation_threshold(now_utc, complaint.priority)

    sla_clock = SLAClock(
        sla_id=f"SLA-{new_cid}",
        complaint_id_fk=complaint.id,
        priority=complaint.priority,
        resolution_hours=policy.resolution_hours,
        first_response_hours=policy.first_response_hours,
        escalation_hours=policy.escalation_hours,
        start_time=now_utc,
        original_deadline=deadline,
        current_deadline=deadline,
        first_response_deadline=first_resp_dl,
        escalation_threshold_time=esc_thresh,
        status="running",
        is_breached=False,
        is_escalated=False,
        created_at=now_utc,
    )
    db.add(sla_clock)

    db.commit()
    db.refresh(complaint)
    return _to_list_item(complaint)


@router.post("/{complaint_id}/messages", response_model=ComplaintMessageSchema, status_code=status.HTTP_201_CREATED)
def create_complaint_message(
    complaint_id: str,
    req: ComplaintMessageCreateRequest,
    db: Session = Depends(get_db),
):
    """Add an interaction message to a complaint thread."""
    if complaint_id.isdigit():
        c = db.scalar(select(Complaint).where(Complaint.id == int(complaint_id)))
    else:
        c = db.scalar(select(Complaint).where(Complaint.complaint_id == complaint_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    msg_count = db.scalar(
        select(func.count(ComplaintMessage.id)).where(ComplaintMessage.complaint_id_fk == c.id)
    ) or 0
    now_utc = datetime.now(timezone.utc)

    msg = ComplaintMessage(
        message_id=f"MSG-{c.complaint_id}-{(msg_count + 1):02d}",
        complaint_id_fk=c.id,
        message_type="customer_message" if req.sender_type == "customer" else "internal_note",
        sender_type=req.sender_type,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        body=req.body,
        channel=req.channel or c.channel,
        is_customer_visible=req.is_customer_visible,
        sequence_number=msg_count + 1,
        delivery_status="delivered",
        sent_at=now_utc,
    )
    c.updated_at = now_utc
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/{complaint_id}", response_model=ComplaintListItem)
def update_complaint(
    complaint_id: str,
    req: ComplaintUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update complaint status or priority, recording lifecycle transition events."""
    if complaint_id.isdigit():
        c = db.scalar(select(Complaint).where(Complaint.id == int(complaint_id)))
    else:
        c = db.scalar(select(Complaint).where(Complaint.complaint_id == complaint_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    now_utc = datetime.now(timezone.utc)
    if req.status and req.status != c.status:
        db.add(ComplaintStatusEvent(
            complaint_id_fk=c.id,
            from_status=c.status,
            to_status=req.status,
            reason=req.notes or f"Status changed to {req.status}",
            changed_by="agent",
            occurred_at=now_utc,
        ))
        c.status = req.status
        if req.status == "escalated":
            c.is_escalated = True
            if c.sla_clock:
                c.sla_clock.is_escalated = True
        elif req.status == "resolved":
            c.resolved_at = now_utc
            if c.sla_clock:
                c.sla_clock.status = "completed"
        elif req.status == "closed":
            c.closed_at = now_utc

    if req.priority:
        c.priority = req.priority

    c.updated_at = now_utc
    db.commit()
    db.refresh(c)
    return _to_list_item(c)


@router.post("/{complaint_id}/resolutions", response_model=ResolutionSchema, status_code=status.HTTP_201_CREATED)
def create_complaint_resolution(
    complaint_id: str,
    req: ComplaintResolutionCreateRequest,
    db: Session = Depends(get_db),
):
    """Record a resolution for a complaint, completing its SLA clock and transitioning to resolved."""
    if complaint_id.isdigit():
        c = db.scalar(select(Complaint).where(Complaint.id == int(complaint_id)))
    else:
        c = db.scalar(select(Complaint).where(Complaint.complaint_id == complaint_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    now_utc = datetime.now(timezone.utc)
    res_id = f"RES-{c.complaint_id}"
    resolution = Resolution(
        resolution_id=res_id,
        complaint_id_fk=c.id,
        resolution_type=req.resolution_type,
        description=req.description,
        refund_amount=req.refund_amount,
        resolved_at=now_utc,
        created_at=now_utc,
    )
    db.add(resolution)

    # Update complaint state
    if c.status != "resolved":
        db.add(ComplaintStatusEvent(
            complaint_id_fk=c.id,
            from_status=c.status,
            to_status="resolved",
            reason=f"Resolved via {req.resolution_type}: {req.description}",
            changed_by="agent",
            occurred_at=now_utc,
        ))
        c.status = "resolved"

    c.resolved_at = now_utc
    c.updated_at = now_utc
    if c.sla_clock:
        c.sla_clock.status = "completed"

    db.commit()
    db.refresh(resolution)
    return resolution


@router.post("/{complaint_id}/surveys", response_model=SurveySchema, status_code=status.HTTP_201_CREATED)
def create_complaint_survey(
    complaint_id: str,
    req: ComplaintSurveyCreateRequest,
    db: Session = Depends(get_db),
):
    """Submit customer satisfaction survey for a complaint."""
    if complaint_id.isdigit():
        c = db.scalar(select(Complaint).where(Complaint.id == int(complaint_id)))
    else:
        c = db.scalar(select(Complaint).where(Complaint.complaint_id == complaint_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    now_utc = datetime.now(timezone.utc)
    survey_count = db.scalar(
        select(func.count(Survey.id)).where(Survey.complaint_id_fk == c.id)
    ) or 0
    survey_id = f"SRV-{c.complaint_id}-{(survey_count + 1):02d}"

    is_before_closure = c.status not in ("closed", "resolved")
    survey = Survey(
        survey_id=survey_id,
        complaint_id_fk=c.id,
        rating=req.rating,
        feedback=req.feedback,
        submitted_by=req.submitted_by or "customer",
        submitted_before_closure=is_before_closure,
        submitted_at=now_utc,
        created_at=now_utc,
    )
    db.add(survey)
    c.updated_at = now_utc
    db.commit()
    db.refresh(survey)
    return survey
