"""Unit tests for the example agent implementations."""
from __future__ import annotations

import pytest

from vclaw.agents.public_service import PublicServiceAgent
from vclaw.agents.task_management import TaskManagementAgent
from vclaw.domain.models.base import AgentCapability, SubTask


def make_subtask(text: str, cap: AgentCapability) -> SubTask:
    return SubTask(
        parent_task_id="parent-1",
        capability=cap,
        input_data={"text": text, "entities": {}},
    )


class TestTaskManagementAgent:
    @pytest.mark.asyncio
    async def test_agent_initializes(self):
        agent = TaskManagementAgent()
        await agent.initialize()
        assert await agent.health_check()
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_execute_create_task(self):
        agent = TaskManagementAgent()
        await agent.initialize()
        subtask = make_subtask(
            "Tạo task 'Fix login bug' cho team backend ưu tiên cao",
            AgentCapability.TASK_MANAGEMENT,
        )
        result = await agent.run(subtask)
        assert result.success
        assert result.agent_id == "task-management-v1"
        assert "message" in result.output or result.output

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_create_task(self):
        agent = TaskManagementAgent()
        await agent.initialize()
        result = await agent.call_tool("create_task", {"title": "My Task", "priority": "high"})
        assert "task_id" in result
        assert result["task_id"]

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_list_tasks(self):
        agent = TaskManagementAgent()
        await agent.initialize()
        await agent.call_tool("create_task", {"title": "Task A"})
        await agent.call_tool("create_task", {"title": "Task B"})
        result = await agent.call_tool("list_tasks", {"limit": 10})
        assert "tasks" in result
        assert result["total"] >= 2

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_update_status(self):
        agent = TaskManagementAgent()
        await agent.initialize()
        created = await agent.call_tool("create_task", {"title": "Status Test"})
        task_id = created["task_id"]
        result = await agent.call_tool(
            "update_task_status", {"task_id": task_id, "new_status": "in_progress"}
        )
        assert result["success"]
        assert result["new_status"] == "in_progress"

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_manifest_valid(self):
        agent = TaskManagementAgent()
        assert agent.manifest.agent_id == "task-management-v1"
        assert AgentCapability.TASK_MANAGEMENT in agent.manifest.capabilities
        assert len(agent.manifest.tools) > 0


class TestPublicServiceAgent:
    @pytest.mark.asyncio
    async def test_agent_initializes(self):
        agent = PublicServiceAgent()
        await agent.initialize()
        assert await agent.health_check()
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_execute_lookup(self):
        agent = PublicServiceAgent()
        await agent.initialize()
        subtask = make_subtask(
            "Thủ tục đổi căn cước công dân",
            AgentCapability.PUBLIC_SERVICE,
        )
        result = await agent.run(subtask)
        assert result.success
        assert result.agent_id == "public-service-v1"

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_lookup_procedure(self):
        agent = PublicServiceAgent()
        await agent.initialize()
        result = await agent.call_tool("lookup_procedure", {"query": "căn cước"})
        assert "procedures" in result
        assert result["total"] > 0

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_track_document(self):
        agent = PublicServiceAgent()
        await agent.initialize()
        result = await agent.call_tool("track_document", {"reference_number": "HS-2024-001"})
        assert "status" in result
        assert "history" in result

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_call_tool_calculate_fee(self):
        agent = PublicServiceAgent()
        await agent.initialize()
        result = await agent.call_tool(
            "calculate_fee", {"procedure_id": "DKKD-001", "quantity": 2}
        )
        assert "fee" in result
        assert result["currency"] == "VND"

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_manifest_valid(self):
        agent = PublicServiceAgent()
        assert agent.manifest.agent_id == "public-service-v1"
        assert AgentCapability.PUBLIC_SERVICE in agent.manifest.capabilities
