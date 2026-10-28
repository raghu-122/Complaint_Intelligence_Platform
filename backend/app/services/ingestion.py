"""
Data Ingestion Service — validates, deduplicates, and persists uploaded CSV/JSON records.
Supports complaints and customers with full row-level error reporting.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.customer import Customer
from app.models.category import Category
from app.models.order import Order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_COMPLAINT_FIELDS = {
    "complaint_id", "subject", "description", "channel", "status", "priority",
}
REQUIRED_CUSTOMER_FIELDS = {
    "customer_id", "first_name", "last_name", "email",
}

VALID_CHANNELS = {"email", "phone", "web", "chat", "social_media", "in_store"}
VALID_STATUSES = {"open", "in_progress", "pending_customer", "escalated", "resolved", "closed", "reopened"}
VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}
VALID_SENTIMENTS = {"positive", "neutral", "negative"}
VALID_ACCOUNT_TIERS = {"standard", "silver", "gold", "platinum"}

COMPLAINT_ID_RE = re.compile(r"^CMP-\d{4}-\d{6}$")
CUSTOMER_ID_RE = re.compile(r"^CUS-\d{6}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IngestionResult:
    """Aggregates per-row results for an ingestion run."""

    def __init__(self) -> None:
        self.accepted: int = 0
        self.rejected: int = 0
        self.skipped_duplicates: int = 0
        self.errors: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "skipped_duplicates": self.skipped_duplicates,
            "total_rows_processed": self.accepted + self.rejected + self.skipped_duplicates,
            "errors": self.errors,
        }


def _row_error(result: IngestionResult, row: int, field: str, message: str) -> None:
    result.errors.append({"row": row, "field": field, "error": message})


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_content(content: bytes, filename: str) -> tuple[list[dict[str, Any]], str | None]:
    """Returns (rows_as_dicts, error_message_or_None)."""
    name_lower = filename.lower()
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        return [], "File must be UTF-8 encoded."

    if name_lower.endswith(".json"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], f"Invalid JSON: {exc}"
        if isinstance(parsed, list):
            return parsed, None
        # Support {"data": [...]} wrapper
        for key in ("data", "records", "rows", "complaints", "customers"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key], None
        return [], "JSON must be an array or an object with a 'data' key containing an array."

    if name_lower.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        try:
            rows = list(reader)
        except csv.Error as exc:
            return [], f"CSV parse error: {exc}"
        return rows, None

    return [], "Unsupported file type. Please upload a .csv or .json file."


def _coerce_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    return str(val).strip().lower() in ("true", "1", "yes")


def _parse_datetime(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Complaint ingestion
# ---------------------------------------------------------------------------

def ingest_complaints(
    content: bytes,
    filename: str,
    db: Session,
) -> IngestionResult:
    """Parse, validate, deduplicate, and persist complaint rows."""
    result = IngestionResult()

    rows, parse_error = _parse_content(content, filename)
    if parse_error:
        result.rejected += 1
        _row_error(result, 0, "_file", parse_error)
        return result

    # Collect existing complaint_ids for dedup
    existing_ids: set[str] = {
        row[0] for row in db.query(Complaint.complaint_id).filter(Complaint.complaint_id.isnot(None)).all()
    }

    # Build category lookup
    categories: dict[str, int] = {
        c.code: c.id for c in db.query(Category).all()
    }
    orders: dict[str, int] = {
        o.order_id: o.id for o in db.query(Order).all()
    }
    customers: dict[str, int] = {
        c.customer_id: c.id for c in db.query(Customer).all()
    }

    to_insert: list[Complaint] = []

    for idx, raw in enumerate(rows, start=1):
        row_num = idx
        row: dict[str, Any] = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}

        # --- Required fields ---
        missing = REQUIRED_COMPLAINT_FIELDS - set(row.keys())
        if missing:
            result.rejected += 1
            _row_error(result, row_num, "schema", f"Missing required fields: {sorted(missing)}")
            continue

        complaint_id = str(row.get("complaint_id", "")).strip()

        # Blank check
        if not complaint_id:
            result.rejected += 1
            _row_error(result, row_num, "complaint_id", "complaint_id cannot be blank.")
            continue

        # Format check (soft — warn but accept non-standard external IDs)
        # Dedup check
        if complaint_id in existing_ids:
            result.skipped_duplicates += 1
            continue

        # Validate enum fields
        channel = str(row.get("channel", "web")).strip().lower()
        if channel not in VALID_CHANNELS:
            result.rejected += 1
            _row_error(result, row_num, "channel", f"'{channel}' is not a valid channel. Valid: {sorted(VALID_CHANNELS)}")
            continue

        status = str(row.get("status", "open")).strip().lower()
        if status not in VALID_STATUSES:
            result.rejected += 1
            _row_error(result, row_num, "status", f"'{status}' is not a valid status.")
            continue

        priority = str(row.get("priority", "P3")).strip().upper()
        if priority not in VALID_PRIORITIES:
            result.rejected += 1
            _row_error(result, row_num, "priority", f"'{priority}' is not a valid priority. Valid: P1/P2/P3/P4.")
            continue

        sentiment_raw = str(row.get("sentiment", "neutral")).strip().lower()
        sentiment = sentiment_raw if sentiment_raw in VALID_SENTIMENTS else "neutral"

        subject = str(row.get("subject", "")).strip()
        if not subject:
            result.rejected += 1
            _row_error(result, row_num, "subject", "subject cannot be blank.")
            continue

        description = str(row.get("description", "")).strip()
        if not description:
            result.rejected += 1
            _row_error(result, row_num, "description", "description cannot be blank.")
            continue

        # FK resolution (soft — allow missing FKs so partial data can be ingested)
        customer_id_fk = None
        cid_raw = str(row.get("customer_id", "")).strip()
        if cid_raw and cid_raw in customers:
            customer_id_fk = customers[cid_raw]

        order_id_fk = None
        oid_raw = str(row.get("order_id", "")).strip()
        if oid_raw and oid_raw in orders:
            order_id_fk = orders[oid_raw]

        category_id_fk = None
        cat_raw = str(row.get("category_code", "")).strip()
        if cat_raw and cat_raw in categories:
            category_id_fk = categories[cat_raw]

        category_code = cat_raw or None

        # Timestamps
        created_at = _parse_datetime(row.get("created_at")) or datetime.now(timezone.utc)
        updated_at = _parse_datetime(row.get("updated_at")) or datetime.now(timezone.utc)

        # Boolean flags
        is_safety_incident = _coerce_bool(row.get("is_safety_incident", row.get("is_safety_issue", False)))
        is_refund_pending = _coerce_bool(row.get("is_refund_pending", False))

        # Numeric
        try:
            sentiment_score = float(row["sentiment_score"]) if row.get("sentiment_score") else None
        except (ValueError, TypeError):
            sentiment_score = None

        obj = Complaint(
            complaint_id=complaint_id,
            customer_id_fk=customer_id_fk,
            order_id_fk=order_id_fk,
            category_id_fk=category_id_fk,
            category_code=category_code,
            subject=subject,
            description=description,
            channel=channel,
            status=status,
            priority=priority,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            is_safety_incident=is_safety_incident,
            is_refund_pending=is_refund_pending,
            created_at=created_at,
            updated_at=updated_at,
        )
        to_insert.append(obj)
        existing_ids.add(complaint_id)

    # Bulk insert with rollback on error
    if to_insert:
        try:
            db.add_all(to_insert)
            db.commit()
            result.accepted = len(to_insert)
        except Exception as exc:
            db.rollback()
            result.rejected += len(to_insert)
            result.errors.append({"row": -1, "field": "_db", "error": f"Database error during commit: {exc}"})

    return result


# ---------------------------------------------------------------------------
# Customer ingestion
# ---------------------------------------------------------------------------

def ingest_customers(
    content: bytes,
    filename: str,
    db: Session,
) -> IngestionResult:
    """Parse, validate, deduplicate, and persist customer rows."""
    result = IngestionResult()

    rows, parse_error = _parse_content(content, filename)
    if parse_error:
        result.rejected += 1
        _row_error(result, 0, "_file", parse_error)
        return result

    existing_ids: set[str] = {
        row[0] for row in db.query(Customer.customer_id).all()
    }
    existing_emails: set[str] = {
        row[0].lower() for row in db.query(Customer.email).all()
    }

    to_insert: list[Customer] = []

    for idx, raw in enumerate(rows, start=1):
        row_num = idx
        row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}

        missing = REQUIRED_CUSTOMER_FIELDS - set(row.keys())
        if missing:
            result.rejected += 1
            _row_error(result, row_num, "schema", f"Missing required fields: {sorted(missing)}")
            continue

        customer_id = str(row.get("customer_id", "")).strip()
        if not customer_id:
            result.rejected += 1
            _row_error(result, row_num, "customer_id", "customer_id cannot be blank.")
            continue

        if customer_id in existing_ids:
            result.skipped_duplicates += 1
            continue

        email = str(row.get("email", "")).strip().lower()
        if not email or not EMAIL_RE.match(email):
            result.rejected += 1
            _row_error(result, row_num, "email", f"'{email}' is not a valid email address.")
            continue

        if email in existing_emails:
            result.skipped_duplicates += 1
            continue

        first_name = str(row.get("first_name", "")).strip()
        last_name = str(row.get("last_name", "")).strip()
        if not first_name or not last_name:
            result.rejected += 1
            _row_error(result, row_num, "name", "first_name and last_name cannot be blank.")
            continue

        account_tier = str(row.get("account_tier", "standard")).strip().lower()
        if account_tier not in VALID_ACCOUNT_TIERS:
            account_tier = "standard"

        vulnerability_flag = _coerce_bool(row.get("vulnerability_flag", False))
        is_active = _coerce_bool(row.get("is_active", True))
        is_synthetic = _coerce_bool(row.get("is_synthetic", False))

        try:
            loyalty_points = int(float(str(row.get("loyalty_points", 0) or 0)))
        except (ValueError, TypeError):
            loyalty_points = 0

        created_at = _parse_datetime(row.get("created_at")) or datetime.now(timezone.utc)
        updated_at = _parse_datetime(row.get("updated_at")) or datetime.now(timezone.utc)

        obj = Customer(
            customer_id=customer_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=str(row.get("phone", "") or "").strip() or None,
            address_line1=str(row.get("address_line1", "") or "").strip() or None,
            city=str(row.get("city", "") or "").strip() or None,
            state=str(row.get("state", "") or "").strip() or None,
            postal_code=str(row.get("postal_code", "") or "").strip() or None,
            country=str(row.get("country", "US") or "US").strip() or "US",
            vulnerability_flag=vulnerability_flag,
            vulnerability_type=str(row.get("vulnerability_type", "") or "").strip() or None,
            is_active=is_active,
            account_tier=account_tier,
            loyalty_points=loyalty_points,
            is_synthetic=is_synthetic,
            created_at=created_at,
            updated_at=updated_at,
        )
        to_insert.append(obj)
        existing_ids.add(customer_id)
        existing_emails.add(email)

    if to_insert:
        try:
            db.add_all(to_insert)
            db.commit()
            result.accepted = len(to_insert)
        except Exception as exc:
            db.rollback()
            result.rejected += len(to_insert)
            result.errors.append({"row": -1, "field": "_db", "error": f"Database error during commit: {exc}"})

    return result
