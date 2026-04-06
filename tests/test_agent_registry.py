"""Tests for agent registry and discovery."""

from __future__ import annotations

from typing import ClassVar

import pytest

from vclaw.agents.base import AgentBase
from vclaw.agents.registry import AgentRegistry
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
)
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus


class MockAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="mock_agent",
        description="A mock agent for testing",
        capabilities=[
            AgentCapability(name="mock_capability", description="Does mock things"),
        ],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"echo": request.input_data.get("text", "")},
        )


@pytest.mark.asyncio
async def test_register_and_get() -> None:
    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry(event_bus=bus)

    agent = MockAgent()
    await registry.register(agent)

    retrieved = registry.get("mock_agent")
    assert retrieved is not None
    assert retrieved.name == "mock_agent"

    await bus.stop()


@pytest.mark.asyncio
async def test_capability_lookup() -> None:
    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry(event_bus=bus)

    await registry.register(MockAgent())

    found = registry.find_by_capability("mock_capability")
    assert len(found) == 1
    assert found[0].name == "mock_agent"

    not_found = registry.find_by_capability("nonexistent")
    assert len(not_found) == 0

    await bus.stop()


@pytest.mark.asyncio
async def test_deregister() -> None:
    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry(event_bus=bus)

    await registry.register(MockAgent())
    assert registry.get("mock_agent") is not None

    await registry.deregister("mock_agent")
    assert registry.get("mock_agent") is None

    await bus.stop()


@pytest.mark.asyncio
async def test_duplicate_register() -> None:
    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry(event_bus=bus)

    await registry.register(MockAgent())
    await registry.register(MockAgent())

    assert len(registry.agents) == 1
    await bus.stop()


@pytest.mark.asyncio
async def test_health_check_all() -> None:
    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry(event_bus=bus)

    await registry.register(MockAgent())

    health = await registry.health_check_all()
    assert health["mock_agent"] is True

    await bus.stop()


@pytest.mark.asyncio
async def test_agent_execution() -> None:
    agent = MockAgent()
    await agent.setup()

    request = AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="mock_agent",
        input_data={"text": "hello world"},
    )

    response = await agent.run(request)
    assert response.success
    assert response.data["echo"] == "hello world"
    assert response.duration_ms > 0
