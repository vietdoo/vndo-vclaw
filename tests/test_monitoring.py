"""Tests for the monitoring API endpoints."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from vclaw.api import monitoring
from vclaw.api.webhook import create_app


@pytest.fixture
def client() -> TestClient:
    routes = monitoring.create_monitoring_routes()
    app = create_app(extra_routes=routes)
    return TestClient(app)


def test_system_stats_no_platform(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/stats/system")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["service"] == "vclaw"


def test_workflow_stats_no_store(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/stats/workflows")
    assert resp.status_code == 503


def test_active_workflows_no_store(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/workflows/active")
    assert resp.status_code == 503


def test_agent_health_no_registry(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/agents/health")
    assert resp.status_code == 503


def test_event_log_no_postgres(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/events")
    assert resp.status_code == 503


def test_workflow_detail_no_store(client: TestClient) -> None:
    monitoring._platform = None
    resp = client.get("/api/v1/workflows/fake-id")
    assert resp.status_code == 503
