"""
ComplaintMessage model — immutable communication history.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class ComplaintMessage(Base):
    __tablename__ = "complaint_messages"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('customer_message', 'internal_note', 'system_event', 'resolution_update')",
            name="ck_message_type_valid"
        ),
        CheckConstraint(
            "sender_type IN ('customer', 'agent', 'system')",
            name="ck_message_sender_type_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: MSG-CMP-2026-000001-001
    message_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)

    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="customer_message")
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)  # customer, agent, system
    sender_id: Mapped[str | None] = mapped_column(String(30), nullable=True)  # customer_id or agent_id
    sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_customer_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Communication status
    delivery_status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # sent, delivered, failed
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sequence number for ordering within a complaint (immutable)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    # Anomaly flag
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ComplaintMessage {self.message_id}: {self.sender_type}>"
