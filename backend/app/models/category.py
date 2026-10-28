"""
Category model — complaint classification categories.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    safety_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    # Relationships
    complaints: Mapped[list["Complaint"]] = relationship("Complaint", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.code}: {self.name}>"
