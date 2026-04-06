"""Task management agent with MCP-compatible tool calling."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog

from vclaw.agents.base import AgentBase
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
    LLMRequest,
    RetryPolicy,
    ToolDefinition,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TaskStore:
    """In-memory Kanban task store (replace with DB in production)."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def create_task(
        self,
        title: str,
        description: str = "",
        assignee: str = "",
        team: str = "",
        priority: str = "medium",
    ) -> dict[str, Any]:
        self._counter += 1
        task_id = f"TASK-{self._counter:04d}"
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": "todo",
            "assignee": assignee,
            "team": team,
            "priority": priority,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._tasks[task_id] = task
        return task

    def update_task(self, task_id: str, **updates: Any) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.update(updates)
        return task

    def move_task(self, task_id: str, status: str) -> dict[str, Any] | None:
        return self.update_task(task_id, status=status)

    def list_tasks(
        self,
        team: str = "",
        status: str = "",
        assignee: str = "",
    ) -> list[dict[str, Any]]:
        tasks = list(self._tasks.values())
        if team:
            tasks = [t for t in tasks if t.get("team", "").lower() == team.lower()]
        if status:
            tasks = [t for t in tasks if t.get("status", "").lower() == status.lower()]
        if assignee:
            tasks = [t for t in tasks if t.get("assignee", "").lower() == assignee.lower()]
        return tasks

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def delete_task(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None


class TaskManagementAgent(AgentBase):
    """Agent for Kanban task management with LLM-powered tool selection.

    Supports: create, update, move, list, get, delete operations.
    Uses structured tool-calling to interpret natural language commands.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="task_management",
        version="0.1.0",
        description="Manages Kanban tasks: create, update, move, list, and delete tasks for teams.",
        capabilities=[
            AgentCapability(
                name="task_management",
                description="Create, update, move, list, and manage Kanban tasks",
            ),
            AgentCapability(
                name="task_creation",
                description="Create new tasks with title, description, assignee, team, priority",
            ),
        ],
        tools=[
            ToolDefinition(
                name="create_task",
                description="Create a new task on the Kanban board",
                parameters={
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "assignee": {"type": "string", "description": "Person assigned to the task"},
                    "team": {"type": "string", "description": "Team owning the task"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Task priority level",
                    },
                },
                required_params=["title"],
            ),
            ToolDefinition(
                name="update_task",
                description="Update an existing task's fields",
                parameters={
                    "task_id": {"type": "string", "description": "Task ID (e.g. TASK-0001)"},
                    "title": {"type": "string", "description": "New title"},
                    "description": {"type": "string", "description": "New description"},
                    "assignee": {"type": "string", "description": "New assignee"},
                    "priority": {"type": "string", "description": "New priority"},
                },
                required_params=["task_id"],
            ),
            ToolDefinition(
                name="move_task",
                description="Move a task to a different status column",
                parameters={
                    "task_id": {"type": "string", "description": "Task ID"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "review", "done"],
                        "description": "Target status",
                    },
                },
                required_params=["task_id", "status"],
            ),
            ToolDefinition(
                name="list_tasks",
                description="List tasks with optional filters",
                parameters={
                    "team": {"type": "string", "description": "Filter by team"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "assignee": {"type": "string", "description": "Filter by assignee"},
                },
                required_params=[],
            ),
            ToolDefinition(
                name="get_task",
                description="Get details of a specific task",
                parameters={
                    "task_id": {"type": "string", "description": "Task ID"},
                },
                required_params=["task_id"],
            ),
            ToolDefinition(
                name="delete_task",
                description="Delete a task from the board",
                parameters={
                    "task_id": {"type": "string", "description": "Task ID"},
                },
                required_params=["task_id"],
            ),
        ],
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=0.5),
        tags=["task", "kanban", "project_management"],
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._store = TaskStore()

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Process task management request using LLM tool calling."""
        text = request.input_data.get("text", "")
        if not text:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text provided",
            )

        tool_schemas = self.get_tool_schemas()

        llm_request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a task management assistant. Use the available tools to "
                        "fulfill the user's request. Always use a tool call - do not respond "
                        "with plain text. Extract parameters from the user message."
                    ),
                },
                {"role": "user", "content": text},
            ],
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.0,
        )

        try:
            llm_response = await self.call_llm(llm_request)
        except Exception as exc:
            return await self._fallback_execution(request, str(exc))

        if llm_response.tool_calls:
            return await self._handle_tool_calls(request, llm_response.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_response.content or "Task operation completed."},
        )

    async def _handle_tool_calls(
        self, request: AgentRequest, tool_calls: list[dict[str, Any]]
    ) -> AgentResponse:
        """Execute tool calls returned by the LLM."""
        results: list[dict[str, Any]] = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = self._execute_tool(name, args)
            results.append({"tool": name, "result": result})

        response_parts = []
        for r in results:
            tool_name = r["tool"]
            tool_result = r["result"]
            if tool_result.get("success"):
                data = tool_result.get("data")
                if isinstance(data, list):
                    if data:
                        lines = [
                            f"  • {t.get('id', '?')}: "
                            f"{t.get('title', '?')} [{t.get('status', '?')}]"
                            for t in data
                        ]
                        header = f"📋 Found {len(data)} task(s):\n"
                        response_parts.append(header + "\n".join(lines))
                    else:
                        response_parts.append("No tasks found matching the criteria.")
                elif isinstance(data, dict):
                    task_id = data.get("id", "")
                    title = data.get("title", "")
                    status = data.get("status", "")
                    if tool_name == "create_task":
                        response_parts.append(f"✅ Created task {task_id}: {title}")
                    elif tool_name == "move_task":
                        response_parts.append(f"➡️ Moved {task_id} to {status}")
                    elif tool_name == "update_task":
                        response_parts.append(f"✏️ Updated task {task_id}")
                    else:
                        response_parts.append(f"📌 {task_id}: {title} [{status}]")
                elif isinstance(data, bool) and data:
                    response_parts.append("🗑️ Task deleted successfully.")
            else:
                response_parts.append(f"❌ {tool_result.get('error', 'Unknown error')}")

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={
                "response_text": "\n".join(response_parts),
                "tool_results": results,
            },
        )

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call to the appropriate store method."""
        try:
            if name == "create_task":
                task = self._store.create_task(**args)
                return {"success": True, "data": task}
            elif name == "update_task":
                task = self._store.update_task(**args)
                if task:
                    return {"success": True, "data": task}
                return {"success": False, "error": f"Task {args.get('task_id')} not found"}
            elif name == "move_task":
                task = self._store.move_task(**args)
                if task:
                    return {"success": True, "data": task}
                return {"success": False, "error": f"Task {args.get('task_id')} not found"}
            elif name == "list_tasks":
                tasks = self._store.list_tasks(**args)
                return {"success": True, "data": tasks}
            elif name == "get_task":
                task = self._store.get_task(args.get("task_id", ""))
                if task:
                    return {"success": True, "data": task}
                return {"success": False, "error": f"Task {args.get('task_id')} not found"}
            elif name == "delete_task":
                deleted = self._store.delete_task(args.get("task_id", ""))
                if deleted:
                    return {"success": True, "data": True}
                return {"success": False, "error": f"Task {args.get('task_id')} not found"}
            else:
                return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        """Fallback when LLM is unavailable: parse simple commands directly."""
        text = request.input_data.get("text", "").lower()

        if any(kw in text for kw in ["tạo task", "create task", "new task", "thêm task"]):
            task = self._store.create_task(
                title=request.input_data.get("text", "Untitled task"),
                team=request.input_data.get("team", ""),
                assignee=request.input_data.get("assignee", ""),
            )
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={
                    "response_text": f"✅ Created task {task['id']}: {task['title']}",
                    "task": task,
                },
                metadata={"fallback": True, "llm_error": error},
            )

        if any(kw in text for kw in ["list tasks", "danh sách", "show tasks"]):
            tasks = self._store.list_tasks()
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={
                    "response_text": f"📋 {len(tasks)} task(s) found.",
                    "tasks": tasks,
                },
                metadata={"fallback": True},
            )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=f"LLM unavailable and no fallback matched. LLM error: {error}",
        )
