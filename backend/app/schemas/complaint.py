"""
Complaint Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseSchema


class ComplaintStatusEventSchema(BaseSchema):
    id: int
    from_status: Optional[str] = None
    to_status: str
    changed_by: Optional[str] = None
    reason: Optional[str] = None
    occurred_at: datetime


class ComplaintMessageSchema(BaseSchema):
    id: int
    message_id: str
    message_type: str
    sender_type: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    body: str
    is_customer_visible: bool
    channel: Optional[str] = None
    delivery_status: Optional[str] = None
    sequence_number: int
    sent_at: datetime


class AssignmentSchema(BaseSchema):
    id: int
    assignment_id: str
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    assignment_type: str
    assigned_by: Optional[str] = None
    reason: Optional[str] = None
    rule_applied: Optional[str] = None
    is_current: bool
    assigned_at: datetime


class SLAClockSchema(BaseSchema):
    id: int
    sla_id: str
    priority: str
    resolution_hours: float
    first_response_hours: float
    escalation_hours: float
    start_time: datetime
    original_deadline: datetime
    current_deadline: datetime
    status: str
    is_breached: bool
    breached_at: Optional[datetime] = None
    is_escalated: bool
    accumulated_paused_hours: float = 0.0


class ResolutionSchema(BaseSchema):
    id: int
    resolution_id: str
    resolution_type: str
    description: str
    refund_amount: Optional[Decimal] = None
    refund_currency: Optional[str] = None
    refund_approved: Optional[bool] = None
    refund_processed_at: Optional[datetime] = None
    resolved_by_agent_id: Optional[str] = None
    resolved_by_team_id: Optional[str] = None
    is_superseded: bool = False
    resolved_at: datetime


class SurveySchema(BaseSchema):
    id: int
    survey_id: str
    rating: int
    feedback: Optional[str] = None
    submitted_by: Optional[str] = None
    submitted_before_closure: bool = False
    submitted_at: datetime


class ComplaintRelationshipSchema(BaseSchema):
    id: int
    primary_complaint_id: str
    related_complaint_id: str
    relationship_type: str
    notes: Optional[str] = None
    created_at: datetime


class ComplaintListItem(BaseSchema):
    id: int
    complaint_id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    order_id: Optional[str] = None
    category_code: Optional[str] = None
    category_name: Optional[str] = None
    subject: str
    description: str
    channel: str
    status: str
    priority: str
    sentiment: str
    sentiment_score: Optional[float] = None
    is_safety_incident: bool
    is_refund_pending: bool
    is_reopened: bool
    reopen_count: int
    is_escalated: bool
    is_anomaly: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assigned_team: Optional[str] = None
    assigned_agent: Optional[str] = None
    sla_status: Optional[str] = None
    sla_breached: Optional[bool] = None


class ComplaintCustomerSummary(BaseSchema):
    customer_id: str
    name: str
    email: str
    account_tier: str
    vulnerability_flag: bool


class ComplaintOrderSummary(BaseSchema):
    order_id: str
    total_amount: str
    status: str
    ordered_at: datetime


class ComplaintCurrentAssignment(BaseSchema):
    agent_name: str
    team_name: str
    assigned_at: datetime


class ComplaintDetail(ComplaintListItem):
    classification_confidence: Optional[float] = None
    classification_evidence: Optional[str] = None
    classification_rule_id: Optional[str] = None
    classification_rule_version: Optional[str] = None
    priority_rule_applied: Optional[str] = None
    priority_explanation: Optional[str] = None
    anomaly_id: Optional[str] = None
    anomaly_type: Optional[str] = None
    
    # Nested entity summaries for UI cards
    customer: Optional[ComplaintCustomerSummary] = None
    order: Optional[ComplaintOrderSummary] = None
    current_assignment: Optional[ComplaintCurrentAssignment] = None

    # Related collections
    status_events: List[ComplaintStatusEventSchema] = []
    messages: List[ComplaintMessageSchema] = []
    assignments: List[AssignmentSchema] = []
    sla_clock: Optional[SLAClockSchema] = None
    resolutions: List[ResolutionSchema] = []
    surveys: List[SurveySchema] = []
    related_complaints: List[ComplaintRelationshipSchema] = []


class ComplaintFilter(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    channel: Optional[str] = None
    category_code: Optional[str] = None
    is_safety_incident: Optional[bool] = None
    is_escalated: Optional[bool] = None
    is_breached: Optional[bool] = None
    customer_id: Optional[str] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
