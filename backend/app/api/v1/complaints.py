"""
Complaints API router.
"""
from __future__ import annotations

import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.complaint import Complaint, ComplaintRelationship
from app.models.assignment import Assignment
from app.schemas.complaint import ComplaintDetail, ComplaintListItem, ComplaintRelationshipSchema
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
        status_events=c.status_events,
        messages=c.messages,
        assignments=assignments_list,
        sla_clock=c.sla_clock,
        resolutions=c.resolutions,
        surveys=c.surveys,
        related_complaints=rels_list,
    )
