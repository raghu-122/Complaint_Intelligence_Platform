"""
Agent model — represents a support agent who handles complaints.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    # Surrogate PK
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: AGT-000001
    agent_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    team_id_fk: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False, default="Agent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_concurrent_cases: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    open_complaint_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="agents")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="agent")

    def __repr__(self) -> str:
        return f"<Agent {self.agent_id}: {self.name}>"
