"""
Customer model.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: CUS-000001
    customer_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="US")

    # Synthetic vulnerability flag - FICTIONAL TEST ATTRIBUTE ONLY
    # This is synthetic data for testing purposes, never represents real vulnerability status
    vulnerability_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vulnerability_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "elderly", "disability"

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    account_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Synthetic data metadata
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")
    complaints: Mapped[list["Complaint"]] = relationship("Complaint", back_populates="customer")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Customer {self.customer_id}: {self.full_name}>"
