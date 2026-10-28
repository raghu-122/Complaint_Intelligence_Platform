"""
Complaint model and associated event/relationship models.
"""
from __future__ import annotations

from sqlalchemy import (
    String, Boolean, Text, DateTime, Numeric, Integer,
    ForeignKey, CheckConstraint, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal

from app.database import Base


# Valid complaint statuses
VALID_STATUSES = (
    "open", "in_progress", "pending_customer", "escalated",
    "resolved", "closed", "reopened"
)
# Valid transitions: from -> set of allowed tos
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "escalated", "closed"},
    "in_progress": {"pending_customer", "escalated", "resolved"},
    "pending_customer": {"in_progress", "escalated", "resolved"},
    "escalated": {"in_progress", "resolved"},
    "resolved": {"closed", "reopened"},
    "closed": {"reopened"},
    "reopened": {"in_progress", "escalated", "resolved"},
}


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            f"status IN {VALID_STATUSES}",
            name="ck_complaint_status_valid"
        ),
        CheckConstraint(
            "priority IN ('P1', 'P2', 'P3', 'P4')",
            name="ck_complaint_priority_valid"
        ),
        CheckConstraint(
            "channel IN ('email', 'phone', 'web', 'chat', 'social_media', 'in_store')",
            name="ck_complaint_channel_valid"
        ),
        CheckConstraint(
            "sentiment IN ('positive', 'neutral', 'negative')",
            name="ck_complaint_sentiment_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: CMP-2026-000001
    complaint_id: Mapped[str] = mapped_column(String(25), unique=True, nullable=False, index=True)

    # Foreign keys (customer is nullable to support anomaly testing)
    customer_id_fk: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    order_id_fk: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    category_id_fk: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)

    # Core fields
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="web")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(5), nullable=False, default="P3")

    # Classification outputs
    category_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    classification_rule_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    classification_rule_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Priority decision
    priority_rule_applied: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sentiment
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Flags
    is_safety_incident: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_refund_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_reopened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Anomaly flag (for anomaly testing layer)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anomaly_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="complaints")
    order: Mapped["Order | None"] = relationship("Order", back_populates="complaints")
    category: Mapped["Category | None"] = relationship("Category", back_populates="complaints")
    messages: Mapped[list["ComplaintMessage"]] = relationship("ComplaintMessage", back_populates="complaint",
                                                               order_by="ComplaintMessage.sent_at")
    status_events: Mapped[list["ComplaintStatusEvent"]] = relationship("ComplaintStatusEvent",
                                                                        back_populates="complaint",
                                                                        order_by="ComplaintStatusEvent.occurred_at")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="complaint",
                                                            order_by="Assignment.assigned_at")
    sla_clock: Mapped["SLAClock | None"] = relationship("SLAClock", back_populates="complaint", uselist=False)
    resolutions: Mapped[list["Resolution"]] = relationship("Resolution", back_populates="complaint",
                                                            order_by="Resolution.resolved_at")
    surveys: Mapped[list["Survey"]] = relationship("Survey", back_populates="complaint")
    related_complaints_as_primary: Mapped[list["ComplaintRelationship"]] = relationship(
        "ComplaintRelationship", foreign_keys="ComplaintRelationship.primary_complaint_id_fk",
        back_populates="primary_complaint"
    )
    related_complaints_as_related: Mapped[list["ComplaintRelationship"]] = relationship(
        "ComplaintRelationship", foreign_keys="ComplaintRelationship.related_complaint_id_fk",
        back_populates="related_complaint"
    )

    def __repr__(self) -> str:
        return f"<Complaint {self.complaint_id}: {self.status}/{self.priority}>"


class ComplaintStatusEvent(Base):
    """Immutable history of complaint status changes."""
    __tablename__ = "complaint_status_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # None for initial creation
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # agent_id or 'system'
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="status_events")


class ComplaintRelationship(Base):
    """Links related complaints — e.g., repeat complaints from same customer."""
    __tablename__ = "complaint_relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('repeat', 'duplicate', 'related', 'escalation_parent')",
            name="ck_rel_type_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    primary_complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)
    related_complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)  # repeat, duplicate, related
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    # Relationships
    primary_complaint: Mapped["Complaint"] = relationship(
        "Complaint", foreign_keys=[primary_complaint_id_fk],
        back_populates="related_complaints_as_primary"
    )
    related_complaint: Mapped["Complaint"] = relationship(
        "Complaint", foreign_keys=[related_complaint_id_fk],
        back_populates="related_complaints_as_related"
    )
