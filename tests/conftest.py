"""Shared test fixtures for the Vclaw test suite (platform + monitoring API)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from vclaw.agents.registry import AgentRegistry
from vclaw.domain.events import CloudEvent
from vclaw.domain.models import IncomingMessage, MessageSource
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus
from vclaw.infrastructure.llm.router import LLMRouter
from vclaw.infrastructure.persistence.state_store import InMemoryStateStore


# ── Vclaw platform fixtures ───────────────────────────────────────────────────

@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def state_store() -> InMemoryStateStore:
    return InMemoryStateStore()


@pytest.fixture
def llm_router() -> LLMRouter:
    return LLMRouter()


@pytest.fixture
def agent_registry(event_bus: InMemoryEventBus, llm_router: LLMRouter) -> AgentRegistry:
    return AgentRegistry(event_bus=event_bus, llm_router=llm_router)


@pytest.fixture
def sample_message() -> IncomingMessage:
    return IncomingMessage(
        source=MessageSource.TELEGRAM,
        chat_id="12345",
        user_id="67890",
        text="Tạo task cho team backend",
    )


@pytest.fixture
def sample_event(sample_message: IncomingMessage) -> CloudEvent:
    return CloudEvent(
        type="vclaw.message.normalized",
        source="vclaw.telegram",
        data=sample_message.model_dump(mode="json"),
        subject=sample_message.chat_id,
    )


# ── Monitoring API fixtures (FastAPI + mocked infra) ─────────────────────────

@pytest_asyncio.fixture
async def api_client():
    """HTTP client for the monitoring/logging FastAPI app with all external deps mocked."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one=MagicMock(return_value=1)))

    async def mock_get_db():
        yield mock_db

    with (
        patch("app.db.base.get_db", mock_get_db),
        patch("app.services.redis_service.get_redis", new_callable=AsyncMock) as mock_redis,
        patch("app.kafka.producer.get_producer", new_callable=AsyncMock),
        patch("app.kafka.producer.start_producer", new_callable=AsyncMock),
        patch("app.kafka.consumer.consumer_manager.start", new_callable=AsyncMock),
        patch("app.kafka.consumer.consumer_manager.stop", new_callable=AsyncMock),
        patch("app.services.redis_service.start_redis", new_callable=AsyncMock),
        patch("app.services.redis_service.stop_redis", new_callable=AsyncMock),
    ):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis.return_value = mock_redis_instance

        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# Backward-compatible alias so existing tests using `client` still work
@pytest_asyncio.fixture
async def client(api_client: AsyncClient) -> AsyncClient:
    return api_client
