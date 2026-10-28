"""
SLAClock and SLAEvent models — track SLA lifecycle for each complaint.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Float, ForeignKey, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class SLAClock(Base):
    __tablename__ = "sla_clocks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'paused', 'breached', 'completed')",
            name="ck_sla_status_valid"
        ),
        CheckConstraint("resolution_hours > 0", name="ck_sla_resolution_hours_positive"),
        CheckConstraint("accumulated_paused_hours >= 0", name="ck_sla_paused_hours_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: SLA-CMP-2026-000001
    sla_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, unique=True, index=True)

    priority: Mapped[str] = mapped_column(String(5), nullable=False)
    resolution_hours: Mapped[float] = mapped_column(Float, nullable=False)
    first_response_hours: Mapped[float] = mapped_column(Float, nullable=False)
    escalation_hours: Mapped[float] = mapped_column(Float, nullable=False)

    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_response_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    escalation_threshold_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Pause tracking
    accumulated_paused_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    is_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Deadline change reason
    deadline_change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Anomaly flag
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    config_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="sla_clock")
    events: Mapped[list["SLAEvent"]] = relationship("SLAEvent", back_populates="sla_clock",
                                                     order_by="SLAEvent.occurred_at")

    def __repr__(self) -> str:
        return f"<SLAClock {self.sla_id}: {self.status}>"


class SLAEvent(Base):
    """Immutable audit log of SLA lifecycle changes."""
    __tablename__ = "sla_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'paused', 'resumed', 'breached', 'escalated', 'completed', 'deadline_extended')",
            name="ck_sla_event_type_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sla_id_fk: Mapped[int] = mapped_column(ForeignKey("sla_clocks.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours_paused: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Anomaly flag
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    sla_clock: Mapped["SLAClock"] = relationship("SLAClock", back_populates="events")
