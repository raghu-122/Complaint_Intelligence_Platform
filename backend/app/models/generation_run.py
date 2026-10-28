"""
GenerationRun model — tracks dataset generation runs for reproducibility.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from app.database import Base


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    scale: Mapped[str] = mapped_column(String(20), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    config_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Record counts
    customer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    complaint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    survey_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Checksums (JSON object)
    checksums: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<GenerationRun {self.run_id}: {self.scale}/{self.seed}>"
