"""
Customers API router.
"""
from __future__ import annotations

import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerDetail, CustomerListItem, CustomerOrderSummary, CustomerComplaintSummary
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=PaginatedResponse[CustomerListItem])
def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    account_tier: Optional[str] = Query(default=None),
    vulnerability_flag: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List customers with search and filtering."""
    query = select(Customer).options(
        selectinload(Customer.complaints),
        selectinload(Customer.orders),
    )

    if account_tier:
        query = query.where(Customer.account_tier == account_tier)
    if vulnerability_flag is not None:
        query = query.where(Customer.vulnerability_flag == vulnerability_flag)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Customer.customer_id.ilike(search_filter),
                Customer.first_name.ilike(search_filter),
                Customer.last_name.ilike(search_filter),
                Customer.email.ilike(search_filter),
                Customer.city.ilike(search_filter),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(Customer.id).offset((page - 1) * page_size).limit(page_size)
    customers = db.scalars(query).all()

    items = [
        CustomerListItem(
            id=c.id,
            customer_id=c.customer_id,
            first_name=c.first_name,
            last_name=c.last_name,
            full_name=c.full_name,
            email=c.email,
            phone=c.phone,
            city=c.city,
            state=c.state,
            country=c.country,
            vulnerability_flag=c.vulnerability_flag,
            vulnerability_type=c.vulnerability_type,
            is_active=c.is_active,
            account_tier=c.account_tier,
            loyalty_points=c.loyalty_points,
            created_at=c.created_at,
            complaints_count=len(c.complaints),
            orders_count=len(c.orders),
        )
        for c in customers
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Get single customer by business ID or numeric ID."""
    query = select(Customer).options(
        selectinload(Customer.complaints),
        selectinload(Customer.orders),
    )

    if customer_id.isdigit():
        c = db.scalar(query.where(Customer.id == int(customer_id)))
    else:
        c = db.scalar(query.where(Customer.customer_id == customer_id))

    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )

    orders = [
        CustomerOrderSummary(
            id=o.id,
            order_id=o.order_id,
            quantity=o.quantity,
            total_amount=o.total_amount,
            currency=o.currency,
            status=o.status,
            ordered_at=o.ordered_at,
            tracking_number=o.tracking_number,
        )
        for o in sorted(c.orders, key=lambda x: str(x.ordered_at), reverse=True)
    ]

    complaints = [
        CustomerComplaintSummary(
            id=comp.id,
            complaint_id=comp.complaint_id,
            subject=comp.subject,
            status=comp.status,
            priority=comp.priority,
            category_code=comp.category_code,
            created_at=comp.created_at,
        )
        for comp in sorted(c.complaints, key=lambda x: str(x.created_at), reverse=True)
    ]

    return CustomerDetail(
        id=c.id,
        customer_id=c.customer_id,
        first_name=c.first_name,
        last_name=c.last_name,
        full_name=c.full_name,
        email=c.email,
        phone=c.phone,
        address_line1=c.address_line1,
        address_line2=c.address_line2,
        city=c.city,
        state=c.state,
        postal_code=c.postal_code,
        country=c.country,
        vulnerability_flag=c.vulnerability_flag,
        vulnerability_type=c.vulnerability_type,
        is_active=c.is_active,
        account_tier=c.account_tier,
        loyalty_points=c.loyalty_points,
        created_at=c.created_at,
        updated_at=c.updated_at,
        complaints_count=len(c.complaints),
        orders_count=len(c.orders),
        orders=orders,
        complaints=complaints,
    )
