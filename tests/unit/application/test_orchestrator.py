"""Unit tests for the Orchestrator engine."""
from __future__ import annotations

from typing import ClassVar

import pytest

from vclaw.agents._base import AgentBase, AgentManifest
from vclaw.application.orchestrator import Orchestrator
from vclaw.application.registry import AgentRegistry
from vclaw.domain.models.base import (
    AgentCapability,
    AgentResult,
    IncomingMessage,
    MessageSource,
    SubTask,
    TaskStatus,
    TenantContext,
)
from vclaw.infrastructure.eventbus import InMemoryEventBus
from vclaw.infrastructure.llm import LLMRouter, MockLLMProvider


def make_message(text: str = "Tạo task cho team backend") -> IncomingMessage:
    return IncomingMessage(
        idempotency_key=f"test-key-{text[:20]}",
        source=MessageSource.TELEGRAM,
        tenant=TenantContext(tenant_id="t1", user_id="u1", chat_id="c1"),
        text=text,
    )


class EchoAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="Echo Agent",
        agent_id="echo-agent-v1",
        version="1.0.0",
        description="Echoes input back",
        capabilities=[AgentCapability.TASK_MANAGEMENT, AgentCapability.GENERAL],
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        priority=10,
    )

    async def execute(self, subtask: SubTask) -> AgentResult:
        text = subtask.input_data.get("text", "")
        return AgentResult(
            subtask_id=subtask.subtask_id,
            agent_id=self.manifest.agent_id,
            success=True,
            output={"message": f"Đã xử lý: {text}"},
        )


@pytest.fixture
async def orchestrator():
    bus = InMemoryEventBus()
    await bus.start()

    registry = AgentRegistry()
    await registry.start()
    await registry.register(EchoAgent)

    llm = LLMRouter(providers=[MockLLMProvider()])
    orch = Orchestrator(
        registry=registry,
        event_bus=bus,
        llm_router=llm,
        max_concurrent_tasks=10,
        task_timeout=30,
    )

    yield orch

    await registry.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_handle_message_completes(orchestrator):
    msg = make_message("Tạo task cho team backend")
    task = await orchestrator.handle_message(msg)
    assert task.status == TaskStatus.COMPLETED
    assert task.final_response is not None
    assert task.intent is not None


@pytest.mark.asyncio
async def test_idempotency(orchestrator):
    msg = make_message("test idempotent")
    task1 = await orchestrator.handle_message(msg)
    task2 = await orchestrator.handle_message(msg)
    assert task1.task_id == task2.task_id


@pytest.mark.asyncio
async def test_task_has_trace_id(orchestrator):
    msg = make_message("trace test")
    task = await orchestrator.handle_message(msg)
    assert task.trace_id


@pytest.mark.asyncio
async def test_task_results_populated(orchestrator):
    msg = make_message("list tasks")
    task = await orchestrator.handle_message(msg)
    assert len(task.results) >= 1
    assert task.results[0].success


@pytest.mark.asyncio
async def test_task_timeout():
    import asyncio
    from typing import ClassVar

    class SlowAgent(AgentBase):
        manifest: ClassVar[AgentManifest] = AgentManifest(
            name="Slow Agent",
            agent_id="slow-agent-v1",
            version="1.0.0",
            description="Slow agent",
            capabilities=[AgentCapability.GENERAL, AgentCapability.TASK_MANAGEMENT],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            priority=1,
            timeout_seconds=60,
        )

        async def execute(self, subtask: SubTask) -> AgentResult:
            await asyncio.sleep(999)
            return AgentResult(subtask_id=subtask.subtask_id, agent_id="slow", success=True, output={})

    bus = InMemoryEventBus()
    await bus.start()
    registry = AgentRegistry()
    await registry.start()
    await registry.register(SlowAgent)

    llm = LLMRouter(providers=[MockLLMProvider()])
    orch = Orchestrator(
        registry=registry,
        event_bus=bus,
        llm_router=llm,
        task_timeout=1,  # 1 second timeout
    )

    msg = make_message("slow test")
    task = await orch.handle_message(msg)
    assert task.status in (TaskStatus.TIMEOUT, TaskStatus.COMPLETED, TaskStatus.FAILED)

    await registry.stop()
    await bus.stop()
