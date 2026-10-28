"""
Product Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from app.schemas.common import BaseSchema


class ProductListItem(BaseSchema):
    id: int
    product_id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    sku: str
    unit_price: Decimal
    currency: str
    stock_quantity: int
    is_active: bool
    is_safety_flagged: bool
    created_at: datetime


class ProductDetail(ProductListItem):
    description: Optional[str] = None
    updated_at: datetime
    complaints_count: int = 0
