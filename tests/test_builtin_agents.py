"""Tests for built-in agents (fallback mode, no LLM required)."""

from __future__ import annotations

import pytest

from vclaw.agents.builtin.public_service.agent import PublicServiceAgent, PublicServiceDirectory
from vclaw.agents.builtin.task_management.agent import TaskManagementAgent, TaskStore
from vclaw.domain.models import AgentRequest


def test_task_store_crud() -> None:
    store = TaskStore()

    task = store.create_task(title="Test task", team="backend", priority="high")
    assert task["id"] == "TASK-0001"
    assert task["status"] == "todo"
    assert task["team"] == "backend"

    updated = store.update_task(task["id"], title="Updated task")
    assert updated is not None
    assert updated["title"] == "Updated task"

    moved = store.move_task(task["id"], "in_progress")
    assert moved is not None
    assert moved["status"] == "in_progress"

    tasks = store.list_tasks(team="backend")
    assert len(tasks) == 1

    retrieved = store.get_task(task["id"])
    assert retrieved is not None

    assert store.delete_task(task["id"]) is True
    assert store.get_task(task["id"]) is None


def test_task_store_list_filters() -> None:
    store = TaskStore()
    store.create_task(title="A", team="frontend", priority="low")
    store.create_task(title="B", team="backend", priority="high")
    store.create_task(title="C", team="backend", priority="low")

    assert len(store.list_tasks(team="backend")) == 2
    assert len(store.list_tasks(team="frontend")) == 1
    assert len(store.list_tasks()) == 3


@pytest.mark.asyncio
async def test_task_agent_fallback_create() -> None:
    agent = TaskManagementAgent()
    await agent.setup()

    request = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="task_management",
        input_data={"text": "Tạo task cho team backend"},
    )

    response = await agent.execute(request)
    assert response.success
    assert "TASK-" in response.data.get("response_text", "")
    assert response.metadata.get("fallback") is True


@pytest.mark.asyncio
async def test_task_agent_fallback_list() -> None:
    agent = TaskManagementAgent()
    await agent.setup()

    request = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="task_management",
        input_data={"text": "list tasks"},
    )

    response = await agent.execute(request)
    assert response.success


def test_public_service_directory() -> None:
    services = PublicServiceDirectory.list_services()
    assert len(services) >= 4

    cccd = PublicServiceDirectory.lookup_service("cccd")
    assert cccd is not None
    assert cccd["processing_days"] == 7


@pytest.mark.asyncio
async def test_public_service_agent_fallback() -> None:
    agent = PublicServiceAgent()
    await agent.setup()

    request = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="public_service",
        input_data={"text": "Thông tin làm passport"},
    )

    response = await agent.execute(request)
    assert response.success
    assert response.metadata.get("fallback") is True


@pytest.mark.asyncio
async def test_public_service_agent_no_match_fallback() -> None:
    agent = PublicServiceAgent()
    await agent.setup()

    request = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="public_service",
        input_data={"text": "random query with no service match"},
    )

    response = await agent.execute(request)
    assert response.success
    assert "dịch vụ công" in response.data.get("response_text", "").lower()
