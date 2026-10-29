"""
Products API router.
"""
from __future__ import annotations

import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductDetail, ProductListItem
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse[ProductListItem])
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: Optional[str] = Query(default=None),
    is_safety_flagged: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List products with filtering and pagination."""
    query = select(Product)

    if category:
        query = query.where(Product.category == category)
    if is_safety_flagged is not None:
        query = query.where(Product.is_safety_flagged == is_safety_flagged)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Product.product_id.ilike(search_filter),
                Product.name.ilike(search_filter),
                Product.brand.ilike(search_filter),
                Product.sku.ilike(search_filter),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(Product.id).offset((page - 1) * page_size).limit(page_size)
    products = db.scalars(query).all()

    items = [
        ProductListItem(
            id=p.id,
            product_id=p.product_id,
            name=p.name,
            category=p.category,
            subcategory=p.subcategory,
            brand=p.brand,
            sku=p.sku,
            unit_price=p.unit_price,
            currency=p.currency,
            stock_quantity=p.stock_quantity,
            is_active=p.is_active,
            is_safety_flagged=p.is_safety_flagged,
            created_at=p.created_at,
        )
        for p in products
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
):
    """Get product detail by business ID or numeric ID."""
    query = select(Product).options(selectinload(Product.order_items))

    if product_id.isdigit():
        p = db.scalar(query.where(Product.id == int(product_id)))
    else:
        p = db.scalar(query.where(Product.product_id == product_id))

    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found",
        )

    # Count complaints associated with this product (via direct product FK)
    complaint_count = len(p.complaints) if hasattr(p, "complaints") else 0

    return ProductDetail(
        id=p.id,
        product_id=p.product_id,
        name=p.name,
        description=p.description,
        category=p.category,
        subcategory=p.subcategory,
        brand=p.brand,
        sku=p.sku,
        unit_price=p.unit_price,
        currency=p.currency,
        stock_quantity=p.stock_quantity,
        is_active=p.is_active,
        is_safety_flagged=p.is_safety_flagged,
        created_at=p.created_at,
        updated_at=p.updated_at,
        complaints_count=complaint_count,
    )
