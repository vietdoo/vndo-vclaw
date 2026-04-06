"""
TaskManagementAgent: Kanban-style task management with MCP-compatible tool definitions.
Supports creating tasks, listing boards, updating status, and assigning team members.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog

from vclaw.agents._base import AgentBase, AgentManifest, ToolDefinition
from vclaw.domain.models.base import (
    AgentCapability,
    AgentResult,
    SubTask,
)
from vclaw.infrastructure.llm import LLMMessage, LLMRouter, MockLLMProvider

logger = structlog.get_logger(__name__)

TOOLS = [
    ToolDefinition(
        name="create_task",
        description="Create a new task on a Kanban board with title, description, assignee, due date, and priority.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Detailed description"},
                "board_id": {"type": "string", "description": "Target board ID"},
                "assignee": {"type": "string", "description": "Username or user ID"},
                "due_date": {"type": "string", "format": "date", "description": "Due date YYYY-MM-DD"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"]},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "url": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    ),
    ToolDefinition(
        name="list_tasks",
        description="List tasks on a board, optionally filtered by status, assignee, or label.",
        input_schema={
            "type": "object",
            "properties": {
                "board_id": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "in_progress", "review", "done"]},
                "assignee": {"type": "string"},
                "label": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "tasks": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    ),
    ToolDefinition(
        name="update_task_status",
        description="Move a task to a new status column on the Kanban board.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "new_status": {"type": "string", "enum": ["todo", "in_progress", "review", "done"]},
                "comment": {"type": "string"},
            },
            "required": ["task_id", "new_status"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "previous_status": {"type": "string"},
                "new_status": {"type": "string"},
            },
        },
    ),
    ToolDefinition(
        name="assign_task",
        description="Assign or reassign a task to a team member.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "assignee": {"type": "string"},
                "notify": {"type": "boolean", "default": True},
            },
            "required": ["task_id", "assignee"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "notified": {"type": "boolean"},
            },
        },
    ),
]

SYSTEM_PROMPT = """You are a task management assistant for the Vclaw platform.
Users communicate in Vietnamese. Understand their intent and use the available tools
to manage Kanban tasks effectively.

Available tools: create_task, list_tasks, update_task_status, assign_task.

Always respond concisely in Vietnamese. When creating tasks, extract:
- Title (required): the main task name
- Description: details if provided
- Assignee: team member mentioned (look for "cho [name]" or "giao [name]")
- Priority: infer from urgency words (gấp/urgent=high, bình thường=normal)
- Due date: parse relative dates (hôm nay=today, ngày mai=tomorrow, tuần sau=next week)"""


class TaskManagementAgent(AgentBase):
    """
    Handles task creation, listing, updates, and assignment on a Kanban board.
    In production, `call_tool` integrates with Linear, Jira, Trello, or custom backends.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="Task Management Agent",
        agent_id="task-management-v1",
        version="1.0.0",
        description="Creates and manages Kanban tasks from natural language commands in Vietnamese",
        capabilities=[AgentCapability.TASK_MANAGEMENT],
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "entities": {"type": "object"},
                "tenant": {"type": "object"},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "task_id": {"type": "string"},
                "action": {"type": "string"},
            },
        },
        tools=TOOLS,
        max_concurrent_tasks=10,
        timeout_seconds=30,
        priority=10,
        tags=["kanban", "productivity", "team"],
        author="vclaw-core",
    )

    def __init__(self) -> None:
        super().__init__()
        self._llm: LLMRouter = LLMRouter(providers=[MockLLMProvider()])
        # In-memory task store for demo; replace with actual API client in production
        self._tasks: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        await super().initialize()
        # In production: initialize Kanban API client here
        # self._linear_client = LinearClient(api_key=config.linear_api_key)

    async def execute(self, subtask: SubTask) -> AgentResult:
        text = subtask.input_data.get("text", "")
        entities = subtask.input_data.get("entities", {})
        tool_calls_made: list[dict[str, Any]] = []

        tools_spec = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self.manifest.tools
        ]

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"User request: {text}\nExtracted entities: {entities}",
            ),
        ]

        response = await self._llm.complete(messages=messages, tools=tools_spec)

        result_output: dict[str, Any] = {}

        if response.tool_calls:
            for tc in response.tool_calls:
                tool_calls_made.append({"tool": tc.name, "args": tc.arguments})
                tool_result = await self.call_tool(tc.name, tc.arguments)
                result_output = tool_result

            final_messages = [
                *messages,
                {"role": "assistant", "content": response.content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": str(tc.arguments)}}
                    for tc in response.tool_calls
                ]},
                *[
                    {"role": "tool", "tool_call_id": tc.id, "content": str(await self.call_tool(tc.name, tc.arguments))}
                    for tc in response.tool_calls
                ],
            ]
            summary_messages = [LLMMessage(**m) if isinstance(m, dict) else m for m in messages]
            summary_messages.append(
                LLMMessage(role="user", content=f"Tool results: {result_output}. Generate a concise Vietnamese reply.")
            )
            summary_response = await self._llm.complete(summary_messages)
            result_output["message"] = summary_response.content or self._default_message(result_output)
        else:
            result_output["message"] = response.content or "Đã xử lý yêu cầu của bạn."

        return AgentResult(
            subtask_id=subtask.subtask_id,
            agent_id=self.manifest.agent_id,
            success=True,
            output=result_output,
            tool_calls_made=tool_calls_made,
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute MCP-compatible tools against the Kanban backend.
        In production, delegate to Linear/Jira/Trello API clients.
        """
        self._logger.debug("tool_call", tool=tool_name, args=arguments)

        if tool_name == "create_task":
            return await self._create_task(arguments)
        elif tool_name == "list_tasks":
            return await self._list_tasks(arguments)
        elif tool_name == "update_task_status":
            return await self._update_task_status(arguments)
        elif tool_name == "assign_task":
            return await self._assign_task(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _create_task(self, args: dict[str, Any]) -> dict[str, Any]:
        task_id = str(uuid.uuid4())[:8].upper()
        task = {
            "task_id": task_id,
            "title": args.get("title", "Untitled"),
            "description": args.get("description", ""),
            "board_id": args.get("board_id", "default"),
            "assignee": args.get("assignee"),
            "due_date": args.get("due_date"),
            "priority": args.get("priority", "normal"),
            "labels": args.get("labels", []),
            "status": "todo",
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._tasks[task_id] = task
        return {
            "task_id": task_id,
            "url": f"https://board.vclaw.ai/tasks/{task_id}",
            "status": "todo",
            "message": f"Đã tạo task #{task_id}: {task['title']}",
            "action": "create_task",
        }

    async def _list_tasks(self, args: dict[str, Any]) -> dict[str, Any]:
        tasks = list(self._tasks.values())
        if status_filter := args.get("status"):
            tasks = [t for t in tasks if t["status"] == status_filter]
        if assignee_filter := args.get("assignee"):
            tasks = [t for t in tasks if t.get("assignee") == assignee_filter]
        limit = args.get("limit", 10)
        return {
            "tasks": tasks[:limit],
            "total": len(tasks),
            "action": "list_tasks",
        }

    async def _update_task_status(self, args: dict[str, Any]) -> dict[str, Any]:
        task_id = args["task_id"]
        new_status = args["new_status"]
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}
        prev = task["status"]
        task["status"] = new_status
        task["updated_at"] = datetime.now(UTC).isoformat()
        return {
            "success": True,
            "previous_status": prev,
            "new_status": new_status,
            "message": f"Task #{task_id} đã chuyển từ '{prev}' sang '{new_status}'",
            "action": "update_task_status",
        }

    async def _assign_task(self, args: dict[str, Any]) -> dict[str, Any]:
        task_id = args["task_id"]
        assignee = args["assignee"]
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}
        task["assignee"] = assignee
        task["updated_at"] = datetime.now(UTC).isoformat()
        notify = args.get("notify", True)
        return {
            "success": True,
            "notified": notify,
            "message": f"Task #{task_id} đã giao cho {assignee}",
            "action": "assign_task",
        }

    @staticmethod
    def _default_message(output: dict[str, Any]) -> str:
        if msg := output.get("message"):
            return msg
        if output.get("task_id"):
            return f"Đã tạo task #{output['task_id']}"
        return "Đã xử lý yêu cầu quản lý task."


# Plugin discovery contract
agent_class = TaskManagementAgent
