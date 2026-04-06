"""
Integration tests: full platform stack with InMemoryEventBus.
Tests the complete message → orchestrator → agent → response pipeline.
"""
from __future__ import annotations

import os

import httpx
import pytest
from asgi_lifespan import LifespanManager

from vclaw.api import create_app
from vclaw.config import Settings

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:token")
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
def test_settings() -> Settings:
    """Minimal settings for integration testing (no external dependencies)."""
    return Settings()


@pytest.fixture
async def test_client(test_settings):
    app = create_app(test_settings)
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "agents" in data


@pytest.mark.asyncio
async def test_ready_endpoint(test_client):
    resp = await test_client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_list_agents_endpoint(test_client):
    resp = await test_client.get("/admin/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    agent_ids = [a["agent_id"] for a in data["agents"]]
    assert "task-management-v1" in agent_ids
    assert "public-service-v1" in agent_ids


@pytest.mark.asyncio
async def test_list_capabilities_endpoint(test_client):
    resp = await test_client.get("/admin/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "task_management" in data["capabilities"]
    assert "public_service" in data["capabilities"]


@pytest.mark.asyncio
async def test_direct_message_api(test_client):
    resp = await test_client.post(
        "/api/v1/message",
        json={
            "text": "Tạo task mới cho team backend",
            "user_id": "user-123",
            "chat_id": "chat-456",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert "response" in data
    assert data["response"] is not None


@pytest.mark.asyncio
async def test_direct_message_empty_text(test_client):
    resp = await test_client.post(
        "/api/v1/message",
        json={"text": "", "user_id": "u1", "chat_id": "c1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_telegram_webhook_no_text_ignored(test_client):
    resp = await test_client.post(
        "/webhook/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 1},
                "chat": {"id": 1},
                "sticker": {},
            },
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_telegram_webhook_invalid_json(test_client):
    resp = await test_client.post(
        "/webhook/telegram",
        content=b"not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
