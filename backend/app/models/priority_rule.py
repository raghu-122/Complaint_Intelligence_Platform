"""
PriorityRule model — versioned priority decision rules.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class PriorityRule(Base):
    __tablename__ = "priority_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority_code: Mapped[str | None] = mapped_column(String(5), nullable=True)  # P1-P4 or null (upgrade)
    priority_upgrade: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # levels to upgrade
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    precedence: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    effective_date: Mapped[str] = mapped_column(String(20), nullable=False, default="2026-01-01")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<PriorityRule {self.rule_id}: {self.name}>"
