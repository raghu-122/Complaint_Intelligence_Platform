"""
Data Ingestion API — CSV/JSON file upload endpoints with validation and deduplication.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ingestion import ingest_complaints, ingest_customers

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_EXTENSIONS = {".csv", ".json"}


def _validate_upload(file: UploadFile) -> None:
    """Raise HTTPException for unsupported file type or size."""
    filename = (file.filename or "").lower()
    if not any(filename.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .csv and .json files are accepted.",
        )


async def _read_file(file: UploadFile) -> bytes:
    """Read file content; enforce size limit."""
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 10 MB size limit ({len(content):,} bytes received).",
        )
    return content


@router.post(
    "/complaints",
    summary="Ingest complaints from CSV or JSON",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def ingest_complaints_endpoint(
    file: UploadFile = File(..., description="CSV or JSON file containing complaint records"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Upload a CSV or JSON file containing complaint records.

    - Validates required fields, enum values, and data types per row.
    - Skips rows that duplicate an existing `complaint_id` (soft-dedup).
    - Commits all valid rows in a single transaction; rolls back on DB error.

    Returns per-row error details for rejected records.
    """
    _validate_upload(file)
    content = await _read_file(file)
    result = ingest_complaints(content, file.filename or "upload.csv", db)
    return result.to_dict()


@router.post(
    "/customers",
    summary="Ingest customers from CSV or JSON",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def ingest_customers_endpoint(
    file: UploadFile = File(..., description="CSV or JSON file containing customer records"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Upload a CSV or JSON file containing customer records.

    - Validates required fields, email format, and enum values per row.
    - Skips rows that duplicate an existing `customer_id` or `email` (soft-dedup).
    - Commits all valid rows in a single transaction; rolls back on DB error.

    Returns per-row error details for rejected records.
    """
    _validate_upload(file)
    content = await _read_file(file)
    result = ingest_customers(content, file.filename or "upload.csv", db)
    return result.to_dict()


@router.get(
    "/schema/complaints",
    summary="Get expected CSV/JSON schema for complaint ingestion",
    response_model=dict,
)
def complaints_schema() -> dict[str, Any]:
    """Returns the required and optional fields for complaint CSV/JSON uploads."""
    return {
        "required_fields": sorted([
            "complaint_id", "subject", "description", "channel", "status", "priority",
        ]),
        "optional_fields": sorted([
            "customer_id", "order_id", "category_code", "sentiment",
            "is_safety_issue", "is_regulatory", "is_synthetic",
            "resolution_time_hours", "created_at", "updated_at",
        ]),
        "enum_values": {
            "channel": ["chat", "email", "in_store", "phone", "social_media", "web"],
            "status": ["closed", "escalated", "in_progress", "open", "pending_customer", "resolved", "reopened"],
            "priority": ["P1", "P2", "P3", "P4"],
            "sentiment": ["negative", "neutral", "positive"],
        },
        "notes": [
            "complaint_id should follow the pattern CMP-YYYY-NNNNNN (e.g. CMP-2026-000001).",
            "Rows with a duplicate complaint_id are silently skipped (deduplicated).",
            "Foreign keys (customer_id, order_id, category_code) are optional; unresolved FKs are stored as NULL.",
        ],
    }


@router.get(
    "/schema/customers",
    summary="Get expected CSV/JSON schema for customer ingestion",
    response_model=dict,
)
def customers_schema() -> dict[str, Any]:
    """Returns the required and optional fields for customer CSV/JSON uploads."""
    return {
        "required_fields": sorted(["customer_id", "email", "first_name", "last_name"]),
        "optional_fields": sorted([
            "phone", "address_line1", "address_line2", "city", "state", "postal_code",
            "country", "account_tier", "loyalty_points", "vulnerability_flag",
            "vulnerability_type", "is_active", "is_synthetic", "created_at", "updated_at",
        ]),
        "enum_values": {
            "account_tier": ["gold", "platinum", "silver", "standard"],
        },
        "notes": [
            "customer_id should follow the pattern CUS-NNNNNN (e.g. CUS-000001).",
            "email must be a valid email address; duplicates are silently skipped.",
            "Rows with a duplicate customer_id or email are silently skipped (deduplicated).",
        ],
    }
