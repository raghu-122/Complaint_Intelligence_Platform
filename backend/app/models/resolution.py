"""
Resolution model — records how a complaint was resolved.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal

from app.database import Base


class Resolution(Base):
    __tablename__ = "resolutions"
    __table_args__ = (
        CheckConstraint(
            "resolution_type IN ('resolved_no_action', 'replacement_sent', 'refund_issued', "
            "'partial_refund', 'apology_credit', 'investigation_closed', 'escalated_to_regulatory', 'other')",
            name="ck_resolution_type_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: RES-CMP-2026-000001
    resolution_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)

    resolution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Refund details
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    refund_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    refund_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    refund_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Responsibility
    resolved_by_agent_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_by_team_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Preserved even if complaint is reopened
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_by_resolution_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="resolutions")

    def __repr__(self) -> str:
        return f"<Resolution {self.resolution_id}: {self.resolution_type}>"
