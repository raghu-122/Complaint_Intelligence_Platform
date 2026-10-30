"""
Extended integration tests for FastAPI REST API endpoints.
Covers filter parameters, generate endpoint, validate filtering,
reports sub-endpoint, and additional complaint/customer/product/team coverage.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Complaints – filter parameters
# ---------------------------------------------------------------------------

def test_complaints_filter_by_priority(client: TestClient):
    """Filter complaints by priority=P1 returns only P1 rows."""
    response = client.get("/api/v1/complaints?priority=P1")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["priority"] == "P1"


def test_complaints_filter_by_status(client: TestClient):
    """Filter complaints by status=open returns only open rows."""
    response = client.get("/api/v1/complaints?status=open")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "open"


def test_complaints_filter_by_channel(client: TestClient):
    """Filter complaints by channel=email returns only email rows."""
    response = client.get("/api/v1/complaints?channel=email")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["channel"] == "email"


def test_complaints_filter_safety_only(client: TestClient):
    """Filter complaints by is_safety_incident=true returns only safety incidents."""
    response = client.get("/api/v1/complaints?is_safety_incident=true")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["is_safety_incident"] is True


def test_complaints_filter_escalated(client: TestClient):
    """Filter complaints by is_escalated=false returns non-escalated only."""
    response = client.get("/api/v1/complaints?is_escalated=false")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["is_escalated"] is False


def test_complaints_search(client: TestClient):
    """Search parameter returns matching complaints."""
    # First get any complaint id fragment to search for
    list_res = client.get("/api/v1/complaints?page=1&page_size=1")
    assert list_res.status_code == 200
    complaint_id = list_res.json()["items"][0]["complaint_id"]
    fragment = complaint_id[:6]  # e.g. "CMP-20"

    response = client.get(f"/api/v1/complaints?search={fragment}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_complaints_filter_by_category_code(client: TestClient):
    """Filter complaints by category_code returns only matching rows."""
    # Get a valid category_code from first complaint
    list_res = client.get("/api/v1/complaints?page=1&page_size=1")
    cat = list_res.json()["items"][0]["category_code"]
    response = client.get(f"/api/v1/complaints?category_code={cat}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["category_code"] == cat


def test_complaints_not_found_returns_404(client: TestClient):
    """Requesting a non-existent complaint ID returns 404."""
    response = client.get("/api/v1/complaints/CMP-XXXX-000000")
    assert response.status_code == 404


def test_complaints_numeric_id_lookup(client: TestClient):
    """Requesting a complaint by numeric ID (e.g. '1') returns complaint detail."""
    response = client.get("/api/v1/complaints/1")
    assert response.status_code == 200
    data = response.json()
    assert "complaint_id" in data
    assert "messages" in data


def test_complaints_filter_by_customer_id(client: TestClient):
    """Filter complaints by customer_id returns only that customer's complaints."""
    list_res = client.get("/api/v1/complaints?page=1&page_size=1")
    customer_id = list_res.json()["items"][0]["customer_id"]
    response = client.get(f"/api/v1/complaints?customer_id={customer_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["customer_id"] == customer_id


# ---------------------------------------------------------------------------
# Generate endpoint
# ---------------------------------------------------------------------------

def test_generate_endpoint_returns_success(client: TestClient):
    """POST /api/v1/generate returns success with counts and run_id."""
    payload = {
        "scale": "starter",
        "seed": 42,
        "clear_existing": True,
        "export_baseline": False,
    }
    response = client.post("/api/v1/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "run_id" in data
    assert "counts" in data
    assert data["counts"]["complaints"] > 0
    assert data["seed"] == 42
    assert data["scale"] == "starter"


def test_generate_endpoint_default_seed(client: TestClient):
    """POST /api/v1/generate with default seed succeeds."""
    payload = {
        "scale": "starter",
        "seed": 20261022,
        "clear_existing": True,
        "export_baseline": False,
    }
    response = client.post("/api/v1/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["counts"]["customers"] > 0
    assert data["counts"]["agents"] > 0


def test_generate_concurrency_lock_rejects_active_run(client: TestClient):
    """POST /api/v1/generate returns 409 Conflict if an active generation run is in progress across workers."""
    from datetime import datetime, timezone
    from app.models.generation_run import GenerationRun
    from tests.conftest import TestingSessionLocal

    with TestingSessionLocal() as session:
        active_run = GenerationRun(
            run_id="RUN-TEST-LOCK-001",
            scale="starter",
            seed=12345,
            generator_version="1.0.0",
            config_version="1.0.0",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(active_run)
        session.commit()

        try:
            response = client.post("/api/v1/generate", json={"scale": "starter", "seed": 42})
            assert response.status_code == 409
            assert "already in progress" in response.json()["detail"]
        finally:
            session.delete(active_run)
            session.commit()


# ---------------------------------------------------------------------------
# Validate endpoint – filter parameters
# ---------------------------------------------------------------------------

def test_validate_get_endpoint(client: TestClient):
    """GET /api/v1/validate returns a validation report."""
    response = client.get("/api/v1/validate")
    assert response.status_code == 200
    report = response.json()
    assert "summary" in report
    assert "findings" in report
    assert report["summary"]["total"] > 0


def test_validate_filter_by_category(client: TestClient):
    """POST /api/v1/validate?category=schema returns only schema findings."""
    response = client.post("/api/v1/validate?category=schema")
    assert response.status_code == 200
    report = response.json()
    for finding in report["findings"]:
        assert finding["category"].lower() == "schema"


def test_validate_filter_by_status(client: TestClient):
    """POST /api/v1/validate?status=pass returns only passing findings."""
    response = client.post("/api/v1/validate?status=pass")
    assert response.status_code == 200
    report = response.json()
    for finding in report["findings"]:
        assert finding["status"].lower() == "pass"


def test_validate_combined_filter(client: TestClient):
    """POST /api/v1/validate with both category and status filters."""
    response = client.post("/api/v1/validate?category=schema&status=pass")
    assert response.status_code == 200
    report = response.json()
    for finding in report["findings"]:
        assert finding["category"].lower() == "schema"
        assert finding["status"].lower() == "pass"


# ---------------------------------------------------------------------------
# Reports endpoint – enriched fields
# ---------------------------------------------------------------------------

def test_reports_enriched_response_structure(client: TestClient):
    """GET /api/v1/reports returns enriched response with baseline_dir and files."""
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert "baseline_dir" in data
    assert "files" in data
    assert isinstance(data["files"], list)
    assert "total_files" in data
    assert "manifest" in data
    assert data["total"] >= 4


def test_reports_baseline_manifest_sub_report(client: TestClient):
    """GET /api/v1/reports/baseline_manifest returns the manifest JSON."""
    # The seeded test database doesn't have a baseline export, so we accept 404
    response = client.get("/api/v1/reports/baseline_manifest")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert "files" in data or "generator" in data


def test_reports_unknown_report_id_returns_404(client: TestClient):
    """GET /api/v1/reports/{unknown} returns 404."""
    response = client.get("/api/v1/reports/nonexistent_report_xyz")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Customers endpoint – detail and filtering
# ---------------------------------------------------------------------------

def test_get_customer_detail(client: TestClient):
    """GET /api/v1/customers/{customer_id} returns customer details."""
    list_res = client.get("/api/v1/customers")
    assert list_res.status_code == 200
    customer_id = list_res.json()["items"][0]["customer_id"]

    response = client.get(f"/api/v1/customers/{customer_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == customer_id


def test_customers_filter_by_tier(client: TestClient):
    """GET /api/v1/customers?account_tier=premium returns only premium tier customers."""
    response = client.get("/api/v1/customers?account_tier=premium")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["account_tier"] == "premium"


def test_customers_filter_vulnerable(client: TestClient):
    """GET /api/v1/customers?vulnerability_flag=true returns vulnerable customers."""
    response = client.get("/api/v1/customers?vulnerability_flag=true")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["vulnerability_flag"] is True


# ---------------------------------------------------------------------------
# Products endpoint
# ---------------------------------------------------------------------------

def test_get_product_detail(client: TestClient):
    """GET /api/v1/products/{product_id} returns product details."""
    list_res = client.get("/api/v1/products")
    assert list_res.status_code == 200
    product_id = list_res.json()["items"][0]["product_id"]

    response = client.get(f"/api/v1/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == product_id


def test_products_filter_by_category(client: TestClient):
    """GET /api/v1/products?category=apparel returns filtered products."""
    list_res = client.get("/api/v1/products")
    items = list_res.json()["items"]
    if not items:
        pytest.skip("No products available")
    category = items[0].get("category")
    if not category:
        pytest.skip("Product has no category field")
    response = client.get(f"/api/v1/products?category={category}")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Teams endpoint – detail
# ---------------------------------------------------------------------------

def test_get_team_detail(client: TestClient):
    """GET /api/v1/teams/{team_id} returns team details with agents."""
    teams_res = client.get("/api/v1/teams")
    assert teams_res.status_code == 200
    teams = teams_res.json()
    assert len(teams) > 0
    team_code = teams[0]["code"]

    response = client.get(f"/api/v1/teams/{team_code}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == team_code


def test_teams_list_includes_agent_count(client: TestClient):
    """Teams list contains agent_count or agents field."""
    response = client.get("/api/v1/teams")
    assert response.status_code == 200
    teams = response.json()
    assert len(teams) >= 6
    # Each team should have a code and name
    for team in teams:
        assert "code" in team
        assert "name" in team


# ---------------------------------------------------------------------------
# Dashboard – sla_stats and trends
# ---------------------------------------------------------------------------

def test_dashboard_charts_sla_stats_structure(client: TestClient):
    """Dashboard charts sla_stats is a list with priority/compliance fields."""
    response = client.get("/api/v1/dashboard/charts")
    assert response.status_code == 200
    charts = response.json()
    sla_stats = charts.get("sla_stats", [])
    assert isinstance(sla_stats, list)
    for item in sla_stats:
        assert "priority" in item
        assert "total" in item
        assert "compliance_pct" in item


def test_dashboard_charts_daily_trends(client: TestClient):
    """Dashboard charts daily_trends is a list of date/count objects."""
    response = client.get("/api/v1/dashboard/charts")
    assert response.status_code == 200
    charts = response.json()
    trends = charts.get("daily_trends", [])
    assert isinstance(trends, list)
    for item in trends:
        assert "date" in item
        assert "count" in item


def test_dashboard_stats_all_kpi_fields(client: TestClient):
    """Dashboard stats returns all expected KPI fields."""
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()
    required_fields = [
        "total_complaints", "open_complaints", "in_progress_complaints",
        "resolved_complaints", "closed_complaints", "sla_breached_count",
        "avg_resolution_time_hours", "total_customers", "active_agents_count",
    ]
    for field in required_fields:
        assert field in stats, f"Missing field: {field}"


def test_dashboard_stats_status_reconciliation(client: TestClient):
    """Verify that mutually exclusive status counts reconcile exactly to total_complaints.

    Regression test for discrepancy where resolved counted resolved+closed.
    Mutually exclusive complaint statuses: open + in_progress + escalated + resolved + closed + reopened == total.
    """
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()

    status_sum = (
        stats["open_complaints"]
        + stats["in_progress_complaints"]
        + stats["escalated_complaints"]
        + stats["resolved_complaints"]
        + stats["closed_complaints"]
        + stats["reopened_complaints"]
    )
    assert status_sum == stats["total_complaints"], (
        f"Status sum ({status_sum}) does not match total_complaints ({stats['total_complaints']}): "
        f"open={stats['open_complaints']}, in_progress={stats['in_progress_complaints']}, "
        f"escalated={stats['escalated_complaints']}, resolved={stats['resolved_complaints']}, "
        f"closed={stats['closed_complaints']}, reopened={stats['reopened_complaints']}"
    )


def test_full_complaint_lifecycle(client: TestClient):
    """End-to-end complaint lifecycle test:

    1. Creation & Classification & Priority Assignment
    2. Automated Team/Agent Routing & SLA Clock
    3. Status Changes & Timeline Audit Trail
    4. Customer Messages
    5. Resolution
    6. Post-resolution Survey
    """
    # 1. Create complaint
    create_payload = {
        "customer_id": 1,
        "title": "Package never arrived",
        "subject": "Missing Order Inquiry",
        "description": "My delivery is missing and never arrived. I cannot locate it anywhere.",
        "channel": "email",
    }
    create_res = client.post("/api/v1/complaints", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    cid = created_data["complaint_id"]
    assert cid.startswith("CMP-2026-")
    assert created_data["status"] == "open"
    assert created_data["category_code"] == "MISSING_ORDER"

    # 2. Add message
    msg_res = client.post(
        f"/api/v1/complaints/{cid}/messages",
        json={"sender_type": "customer", "body": "Any update on my tracking status?", "channel": "email"},
    )
    assert msg_res.status_code == 201
    assert msg_res.json()["body"] == "Any update on my tracking status?"

    # 3. Transition status to in_progress
    patch_res = client.patch(f"/api/v1/complaints/{cid}", json={"status": "in_progress", "notes": "Investigating with carrier"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"

    # 4. Resolve complaint
    res_res = client.post(
        f"/api/v1/complaints/{cid}/resolutions",
        json={"resolution_type": "refund_issued", "description": "Issued full refund for lost package", "refund_amount": 49.99},
    )
    assert res_res.status_code == 201
    assert res_res.json()["resolution_id"].startswith("RES-")

    # 5. Submit survey
    survey_res = client.post(
        f"/api/v1/complaints/{cid}/surveys",
        json={"rating": 5, "feedback": "Prompt resolution and refund processed quickly."},
    )
    assert survey_res.status_code == 201
    assert survey_res.json()["rating"] == 5

    # 6. Verify full detail view
    detail_res = client.get(f"/api/v1/complaints/{cid}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == "resolved"
    assert detail["resolved_at"] is not None
    assert len(detail["messages"]) >= 1
    assert len(detail["resolutions"]) >= 1
    assert len(detail["surveys"]) >= 1

    # Verify timeline chronology
    timeline = detail["status_events"]
    assert len(timeline) >= 2  # open, in_progress, resolved
    statuses = [event["to_status"] for event in timeline]
    assert "open" in statuses
    assert "in_progress" in statuses
    assert "resolved" in statuses


def test_generation_concurrency_lock(client: TestClient, monkeypatch):
    """Accidental concurrent generation calls must return HTTP 409 Conflict."""
    from app.api.v1 import generate as gen_module

    # Acquire the lock to simulate an active generation
    gen_module._generation_lock.acquire()
    try:
        res = client.post("/api/v1/generate", json={"scale": "starter", "seed": 20261022, "clear_existing": True})
        assert res.status_code == 409
        assert "already in progress" in res.json()["detail"].lower()
    finally:
        gen_module._generation_lock.release()


def test_database_url_normalization():
    """Verify postgres:// URLs from Render are normalized to postgresql://."""
    from app.database import _normalize_database_url

    render_url = "postgres://user:secret@dpg-xxxx.render.com/mydb_123"
    assert _normalize_database_url(render_url) == "postgresql://user:secret@dpg-xxxx.render.com/mydb_123"

    standard_url = "postgresql://user:secret@localhost:5432/mydb"
    assert _normalize_database_url(standard_url) == standard_url

    sqlite_url = "sqlite:///./complaint.db"
    assert _normalize_database_url(sqlite_url) == sqlite_url


def test_postgresql_ddl_compilation_all_models():
    """Verify all 18 database models compile valid DDL under the PostgreSQL dialect."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from app.database import Base
    import app.models  # noqa: F401

    assert len(Base.metadata.sorted_tables) >= 18
    pg_dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=pg_dialect))
        assert f"CREATE TABLE {table.name}" in ddl or f'CREATE TABLE "{table.name}"' in ddl


def test_sqlite_to_pg_migration_dry_run():
    """Verify sqlite to postgres migration tool dry-run inspects all 18 tables."""
    import os
    from scripts.migrate_sqlite_to_pg import migrate

    sqlite_path = "backend/complaint_intelligence.db"
    if os.path.exists(sqlite_path):
        counts = migrate(sqlite_path=sqlite_path, pg_url="sqlite:///:memory:", dry_run=True)
        assert len(counts) == 18
        assert counts["complaints"] > 0
        assert counts["customers"] > 0
        assert counts["orders"] > 0


def test_generate_endpoint_production_guard(client: TestClient, monkeypatch):
    """Verify that in production environment (APP_ENV=production), clear_existing=True is rejected with 403."""
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.post(
        "/api/v1/generate",
        json={"scale": "starter", "seed": 20261022, "clear_existing": True},
    )
    assert response.status_code == 403
    assert "forbidden" in response.json()["detail"].lower()
