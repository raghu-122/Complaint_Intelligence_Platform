"""
Customer Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class CustomerOrderSummary(BaseSchema):
    id: int
    order_id: str
    quantity: int
    total_amount: Decimal
    currency: str
    status: str
    ordered_at: datetime
    tracking_number: Optional[str] = None


class CustomerComplaintSummary(BaseSchema):
    id: int
    complaint_id: str
    subject: str
    status: str
    priority: str
    category_code: Optional[str] = None
    created_at: datetime


class CustomerListItem(BaseSchema):
    id: int
    customer_id: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    vulnerability_flag: bool
    vulnerability_type: Optional[str] = None
    is_active: bool
    account_tier: str
    loyalty_points: int
    created_at: datetime
    complaints_count: int = 0
    orders_count: int = 0


class CustomerDetail(CustomerListItem):
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    updated_at: datetime
    orders: List[CustomerOrderSummary] = []
    complaints: List[CustomerComplaintSummary] = []
