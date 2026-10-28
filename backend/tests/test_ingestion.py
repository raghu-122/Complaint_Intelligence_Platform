"""
Tests for the data ingestion pipeline (POST /api/v1/ingest/complaints and /customers).
"""
from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def _json_bytes(rows: list[dict]) -> bytes:
    return json.dumps(rows).encode()


# Minimal valid complaint row
_COMPLAINT_ROW = {
    "complaint_id": "CMP-2099-000001",
    "subject": "Test subject",
    "description": "Test description for ingestion test",
    "channel": "email",
    "status": "open",
    "priority": "P3",
}

# Minimal valid customer row
_CUSTOMER_ROW = {
    "customer_id": "CUS-999001",
    "first_name": "Alice",
    "last_name": "Tester",
    "email": "alice.tester.ingest@example.com",
    "account_tier": "standard",
}


# ---------------------------------------------------------------------------
# Schema discovery endpoints
# ---------------------------------------------------------------------------

class TestIngestionSchema:
    def test_complaint_schema(self, client: TestClient):
        r = client.get("/api/v1/ingest/schema/complaints")
        assert r.status_code == 200
        data = r.json()
        assert "required_fields" in data
        assert "complaint_id" in data["required_fields"]
        assert "enum_values" in data

    def test_customer_schema(self, client: TestClient):
        r = client.get("/api/v1/ingest/schema/customers")
        assert r.status_code == 200
        data = r.json()
        assert "required_fields" in data
        assert "email" in data["required_fields"]


# ---------------------------------------------------------------------------
# Complaint ingestion — CSV
# ---------------------------------------------------------------------------

class TestComplaintIngestionCSV:
    def test_ingest_valid_csv(self, client: TestClient):
        content = _csv_bytes([_COMPLAINT_ROW])
        r = client.post(
            "/api/v1/ingest/complaints",
            files={"file": ("complaints.csv", content, "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0

    def test_ingest_duplicate_csv(self, client: TestClient):
        """Second upload of the same complaint_id must be skipped (dedup)."""
        content = _csv_bytes([_COMPLAINT_ROW])
        # first upload
        client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        # second upload
        r = client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] == 0
        assert data["skipped_duplicates"] == 1

    def test_ingest_invalid_channel(self, client: TestClient):
        row = {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000010", "channel": "fax"}
        content = _csv_bytes([row])
        r = client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        data = r.json()
        assert data["rejected"] == 1
        assert any("channel" in e["field"] for e in data["errors"])

    def test_ingest_invalid_priority(self, client: TestClient):
        row = {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000011", "priority": "P9"}
        content = _csv_bytes([row])
        r = client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        data = r.json()
        assert data["rejected"] == 1

    def test_ingest_missing_required_field(self, client: TestClient):
        row = {"complaint_id": "CMP-2099-000020", "channel": "web"}  # missing subject/description/status/priority
        content = _csv_bytes([row])
        r = client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        data = r.json()
        assert data["rejected"] == 1

    def test_ingest_mixed_valid_invalid(self, client: TestClient):
        rows = [
            {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000030"},
            {"complaint_id": "CMP-2099-000031", "channel": "bad_channel", "subject": "x", "description": "y", "status": "open", "priority": "P3"},
            {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000032"},
        ]
        content = _csv_bytes(rows)
        r = client.post("/api/v1/ingest/complaints", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] == 2
        assert data["rejected"] == 1

    def test_ingest_unsupported_extension(self, client: TestClient):
        r = client.post(
            "/api/v1/ingest/complaints",
            files={"file": ("data.xlsx", b"fake", "application/octet-stream")},
        )
        assert r.status_code == 415


# ---------------------------------------------------------------------------
# Complaint ingestion — JSON
# ---------------------------------------------------------------------------

class TestComplaintIngestionJSON:
    def test_ingest_valid_json_array(self, client: TestClient):
        row = {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000050"}
        content = _json_bytes([row])
        r = client.post(
            "/api/v1/ingest/complaints",
            files={"file": ("complaints.json", content, "application/json")},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1

    def test_ingest_valid_json_wrapped(self, client: TestClient):
        row = {**_COMPLAINT_ROW, "complaint_id": "CMP-2099-000051"}
        content = json.dumps({"data": [row]}).encode()
        r = client.post(
            "/api/v1/ingest/complaints",
            files={"file": ("complaints.json", content, "application/json")},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1

    def test_ingest_malformed_json(self, client: TestClient):
        r = client.post(
            "/api/v1/ingest/complaints",
            files={"file": ("bad.json", b"{not valid json", "application/json")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["rejected"] >= 1


# ---------------------------------------------------------------------------
# Customer ingestion
# ---------------------------------------------------------------------------

class TestCustomerIngestion:
    def test_ingest_valid_customer_csv(self, client: TestClient):
        content = _csv_bytes([_CUSTOMER_ROW])
        r = client.post(
            "/api/v1/ingest/customers",
            files={"file": ("customers.csv", content, "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] == 1

    def test_ingest_duplicate_customer(self, client: TestClient):
        content = _csv_bytes([_CUSTOMER_ROW])
        client.post("/api/v1/ingest/customers", files={"file": ("c.csv", content, "text/csv")})
        r = client.post("/api/v1/ingest/customers", files={"file": ("c.csv", content, "text/csv")})
        assert r.status_code == 200
        assert r.json()["skipped_duplicates"] == 1

    def test_ingest_invalid_email(self, client: TestClient):
        row = {**_CUSTOMER_ROW, "customer_id": "CUS-999002", "email": "not-an-email"}
        content = _csv_bytes([row])
        r = client.post(
            "/api/v1/ingest/customers",
            files={"file": ("customers.csv", content, "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["rejected"] == 1
        assert any("email" in e["field"] for e in data["errors"])

    def test_ingest_missing_name(self, client: TestClient):
        row = {**_CUSTOMER_ROW, "customer_id": "CUS-999003", "email": "x3@example.com", "first_name": ""}
        content = _csv_bytes([row])
        r = client.post(
            "/api/v1/ingest/customers",
            files={"file": ("customers.csv", content, "text/csv")},
        )
        assert r.status_code == 200
        assert r.json()["rejected"] == 1

    def test_ingest_valid_customer_json(self, client: TestClient):
        row = {**_CUSTOMER_ROW, "customer_id": "CUS-999010", "email": "json.ingest@example.com"}
        content = _json_bytes([row])
        r = client.post(
            "/api/v1/ingest/customers",
            files={"file": ("customers.json", content, "application/json")},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1
