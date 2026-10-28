"""
Assignment model — records every ownership change as an immutable history entry.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_type IN ('initial', 'reassignment', 'escalation', 'auto')",
            name="ck_assignment_type_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: ASN-CMP-2026-000001-001
    assignment_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)
    team_id_fk: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    agent_id_fk: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)

    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="initial")
    assigned_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # agent_id or 'system'
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_applied: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="assignments")
    team: Mapped["Team | None"] = relationship("Team", back_populates="assignments")
    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="assignments")

    def __repr__(self) -> str:
        return f"<Assignment {self.assignment_id}: {self.assignment_type}>"
