"""
Vclaw Agent SDK Template — Copy this folder to create a new agent.

Steps:
  1. Copy this folder: cp -r sdk/templates/my_custom_agent vclaw/agents/my_agent
  2. Rename and fill in the manifest fields below.
  3. Implement execute() with your business logic.
  4. Add any MCP-compatible tools to TOOLS list and implement call_tool().
  5. Set agent_class = MyCustomAgent at the bottom (required for auto-discovery).
  6. Run: python scripts/validate_agent.py vclaw/agents/my_agent to validate.

No changes to core code required.
"""
from __future__ import annotations

from typing import Any, ClassVar

import structlog

from vclaw.agents._base import AgentBase, AgentManifest, ToolDefinition
from vclaw.domain.models.base import AgentCapability, AgentResult, SubTask

logger = structlog.get_logger(__name__)

# ── 1. Define your MCP tools (optional) ─────────────────────────────────────

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="my_tool",
        description="Describe what this tool does clearly. The LLM will read this.",
        input_schema={
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First parameter"},
                "param2": {"type": "integer", "description": "Second parameter"},
            },
            "required": ["param1"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "string"},
            },
        },
    ),
]


# ── 2. Implement your agent ──────────────────────────────────────────────────

class MyCustomAgent(AgentBase):
    """
    Replace this docstring with a description of what your agent does.
    This is shown in the admin /admin/agents endpoint.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="My Custom Agent",              # Human-readable name
        agent_id="my-custom-agent-v1",       # Unique ID (kebab-case, versioned)
        version="1.0.0",
        description="Describe what this agent does in 1-2 sentences.",
        capabilities=[AgentCapability.GENERAL],  # Pick from AgentCapability enum
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "entities": {"type": "object"},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "data": {"type": "object"},
            },
        },
        tools=TOOLS,
        max_concurrent_tasks=5,    # Semaphore limit
        timeout_seconds=30,        # Hard timeout per execution
        priority=100,              # Lower = higher priority. 10=high, 100=normal, 200=low
        tags=["my-tag"],
        author="your-name",
        requires_config=[],        # List env var names your agent needs
    )

    async def initialize(self) -> None:
        await super().initialize()
        # One-time setup: connect to external APIs, load models, etc.
        # Example:
        # self._api_client = MyAPIClient(api_key=os.environ["MY_API_KEY"])

    async def execute(self, subtask: SubTask) -> AgentResult:
        """
        Core business logic. Called by the AgentRuntime for each assigned subtask.

        subtask.input_data contains:
          - "text": original user message
          - "entities": extracted entities from intent classification
          - "tenant": tenant context dict
          - Any additional data from task decomposition

        Return AgentResult with:
          - success=True/False
          - output: dict with at minimum a "message" key for Telegram reply
          - error_message: set this on failure
        """
        text = subtask.input_data.get("text", "")
        self._logger.info("executing_subtask", subtask_id=subtask.subtask_id, text_preview=text[:50])

        try:
            # Call your tool
            result = await self.call_tool("my_tool", {"param1": text})

            return AgentResult(
                subtask_id=subtask.subtask_id,
                agent_id=self.manifest.agent_id,
                success=True,
                output={
                    "message": f"Processed: {result.get('result', 'done')}",
                    "data": result,
                },
            )
        except Exception as exc:
            return AgentResult(
                subtask_id=subtask.subtask_id,
                agent_id=self.manifest.agent_id,
                success=False,
                error_message=str(exc),
                error_code="MY_AGENT_ERROR",
            )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool calls to your backend integrations."""
        if tool_name == "my_tool":
            return await self._my_tool_impl(arguments)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _my_tool_impl(self, args: dict[str, Any]) -> dict[str, Any]:
        """Replace with actual implementation."""
        param1 = args.get("param1", "")
        return {"result": f"Echo: {param1}"}

    async def shutdown(self) -> None:
        """Clean up resources: close API clients, flush buffers, etc."""
        await super().shutdown()

    async def health_check(self) -> bool:
        """Return False if your external dependency is unreachable."""
        return True


# ── 3. Required: expose agent_class for auto-discovery ───────────────────────
agent_class = MyCustomAgent
