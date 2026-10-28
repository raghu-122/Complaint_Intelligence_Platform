"""
Order model.
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, DateTime, Numeric, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from decimal import Decimal

from app.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_unit_price_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_order_total_amount_non_negative"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'returned')",
            name="ck_order_status_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Business ID: ORD-2026-000001
    order_id: Mapped[str] = mapped_column(String(25), unique=True, nullable=False, index=True)

    customer_id_fk: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    product_id_fk: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # derived: qty*unit_price - discount
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
    complaints: Mapped[list["Complaint"]] = relationship("Complaint", back_populates="order")

    def __repr__(self) -> str:
        return f"<Order {self.order_id}: customer={self.customer_id_fk}>"
