"""
Integration tests for FastAPI REST API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Verify /health returns 200 OK and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_list_complaints(client: TestClient):
    """Verify complaint listing endpoint returns paginated results."""
    response = client.get("/api/v1/complaints?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 10
    assert data["page"] == 1


def test_get_complaint_detail(client: TestClient):
    """Verify complaint detail endpoint returns full complaint with related entities."""
    # First get a valid complaint_id from the list
    list_res = client.get("/api/v1/complaints?page=1&page_size=1")
    complaint_id = list_res.json()["items"][0]["complaint_id"]

    detail_res = client.get(f"/api/v1/complaints/{complaint_id}")
    assert detail_res.status_code == 200
    comp = detail_res.json()
    assert comp["complaint_id"] == complaint_id
    assert "messages" in comp
    assert "status_events" in comp
    assert "assignments" in comp


def test_list_customers(client: TestClient):
    """Verify customer listing endpoint returns results."""
    response = client.get("/api/v1/customers")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["items"]) > 0


def test_list_products(client: TestClient):
    """Verify product listing endpoint."""
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0


def test_teams_and_agents(client: TestClient):
    """Verify teams and agents endpoints return active squads."""
    teams_res = client.get("/api/v1/teams")
    assert teams_res.status_code == 200
    assert len(teams_res.json()) >= 6

    agents_res = client.get("/api/v1/agents")
    assert agents_res.status_code == 200
    assert len(agents_res.json()) >= 12


def test_dashboard_stats_and_charts(client: TestClient):
    """Verify dashboard stats and charts endpoints return KPI aggregates."""
    stats_res = client.get("/api/v1/dashboard/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_complaints"] > 0
    assert stats["total_customers"] > 0

    charts_res = client.get("/api/v1/dashboard/charts")
    assert charts_res.status_code == 200
    charts = charts_res.json()
    assert len(charts["category_breakdown"]) > 0
    assert len(charts["priority_breakdown"]) > 0
    assert "sla_stats" in charts


def test_validate_endpoint(client: TestClient):
    """Verify validate endpoint executes all checks and returns report."""
    response = client.post("/api/v1/validate")
    assert response.status_code == 200
    report = response.json()
    assert report["summary"]["total"] > 0
    assert report["summary"]["failed"] == 0


def test_anomalies_endpoint(client: TestClient):
    """Verify anomalies endpoint scans database and returns detection result."""
    response = client.get("/api/v1/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert "detected_count" in data
    assert "anomalies" in data


def test_reports_endpoint(client: TestClient):
    """Verify reports endpoint lists available reports."""
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 4
