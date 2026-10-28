"""
Team model — represents a support team with specializations.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    # Surrogate PK
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: TM-001
    team_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specializations: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array as string
    handles_priority: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    safety_capable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="team")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="team")

    def __repr__(self) -> str:
        return f"<Team {self.team_id}: {self.name}>"
