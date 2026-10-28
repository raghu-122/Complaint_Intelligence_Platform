"""
Survey model — post-resolution customer satisfaction survey.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_survey_rating_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: SRV-CMP-2026-000001
    survey_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    complaint_id_fk: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False, index=True)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # customer_id

    # Survey must normally be submitted after complaint is closed
    submitted_before_closure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Flag if this is a deliberate anomaly (survey before closure)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="surveys")

    def __repr__(self) -> str:
        return f"<Survey {self.survey_id}: rating={self.rating}>"
