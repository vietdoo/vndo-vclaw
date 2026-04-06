"""Shared test fixtures for the Vclaw test suite."""

from __future__ import annotations

import pytest

from vclaw.agents.registry import AgentRegistry
from vclaw.domain.events import CloudEvent
from vclaw.domain.models import IncomingMessage, MessageSource
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus
from vclaw.infrastructure.llm.router import LLMRouter
from vclaw.infrastructure.persistence.state_store import InMemoryStateStore


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
