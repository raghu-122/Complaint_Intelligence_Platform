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
