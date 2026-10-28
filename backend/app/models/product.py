"""
Product model.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Numeric, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_product_unit_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_product_stock_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: PRD-000001
    product_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. Electronics, Clothing
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_safety_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    order_items: Mapped[list["Order"]] = relationship("Order", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product {self.product_id}: {self.name}>"
