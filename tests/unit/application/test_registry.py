"""Unit tests for the AgentRegistry."""
from __future__ import annotations

from typing import Any, ClassVar

import pytest

from vclaw.agents._base import AgentBase, AgentManifest
from vclaw.application.registry import AgentRegistry
from vclaw.domain.exceptions import AgentNotFoundError
from vclaw.domain.models.base import AgentCapability, AgentResult, SubTask


class FakeAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="Fake Agent",
        agent_id="fake-agent-v1",
        version="1.0.0",
        description="Test agent",
        capabilities=[AgentCapability.GENERAL],
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        priority=50,
    )

    async def execute(self, subtask: SubTask) -> AgentResult:
        return AgentResult(
            subtask_id=subtask.subtask_id,
            agent_id=self.manifest.agent_id,
            success=True,
            output={"message": "fake done"},
        )


class HighPriorityAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="High Priority Agent",
        agent_id="high-priority-agent-v1",
        version="1.0.0",
        description="High priority test agent",
        capabilities=[AgentCapability.GENERAL],
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        priority=10,  # Higher priority (lower number)
    )

    async def execute(self, subtask: SubTask) -> AgentResult:
        return AgentResult(
            subtask_id=subtask.subtask_id,
            agent_id=self.manifest.agent_id,
            success=True,
            output={"message": "high priority done"},
        )


@pytest.mark.asyncio
async def test_register_and_get_agent():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)

    agent = registry.get_agent("fake-agent-v1")
    assert isinstance(agent, FakeAgent)

    await registry.stop()


@pytest.mark.asyncio
async def test_get_agents_for_capability():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)

    agents = registry.get_agents_for_capability(AgentCapability.GENERAL)
    assert len(agents) == 1
    assert isinstance(agents[0], FakeAgent)

    await registry.stop()


@pytest.mark.asyncio
async def test_priority_ordering():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)
    await registry.register(HighPriorityAgent)

    best = registry.best_agent_for_capability(AgentCapability.GENERAL)
    assert isinstance(best, HighPriorityAgent)

    await registry.stop()


@pytest.mark.asyncio
async def test_agent_not_found_raises():
    registry = AgentRegistry()
    await registry.start()

    with pytest.raises(AgentNotFoundError):
        registry.best_agent_for_capability(AgentCapability.ANALYTICS)

    await registry.stop()


@pytest.mark.asyncio
async def test_deregister():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)
    assert registry.get_agent("fake-agent-v1")

    await registry.deregister("fake-agent-v1")
    with pytest.raises(AgentNotFoundError):
        registry.get_agent("fake-agent-v1")

    await registry.stop()


@pytest.mark.asyncio
async def test_list_agents():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)

    agents = registry.list_agents()
    assert len(agents) == 1
    assert agents[0]["agent_id"] == "fake-agent-v1"
    assert agents[0]["healthy"] is True

    await registry.stop()


@pytest.mark.asyncio
async def test_all_capabilities():
    registry = AgentRegistry()
    await registry.start()
    await registry.register(FakeAgent)

    caps = registry.all_capabilities()
    assert "general" in caps

    await registry.stop()
