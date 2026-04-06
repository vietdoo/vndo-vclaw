"""Agent base class, manifest schema, and SDK contract."""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import structlog
from pydantic import BaseModel, Field

from vclaw.domain.models.base import AgentCapability, AgentResult, SubTask

logger = structlog.get_logger(__name__)


class ToolDefinition(BaseModel):
    """MCP-compatible tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = Field(default_factory=dict)


class AgentManifest(BaseModel):
    """
    Declarative metadata for agent discovery and routing.
    Every agent module must expose a `manifest` instance of this class.
    """

    name: str
    agent_id: str
    version: str
    description: str
    capabilities: list[AgentCapability]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tools: list[ToolDefinition] = Field(default_factory=list)
    max_concurrent_tasks: int = 5
    timeout_seconds: int = 30
    priority: int = 100
    tags: list[str] = Field(default_factory=list)
    author: str = ""
    requires_config: list[str] = Field(default_factory=list)


class AgentBase(ABC):
    """
    Abstract base class for all Vclaw agents.

    Subclass this, implement `execute()`, and expose a `manifest` at module level.
    The AgentRuntime will discover, validate, and manage the lifecycle.
    """

    manifest: ClassVar[AgentManifest]

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)
        self._semaphore: asyncio.Semaphore | None = None

    async def initialize(self) -> None:
        """Called once by the runtime after registration. Override for setup."""
        self._semaphore = asyncio.Semaphore(self.manifest.max_concurrent_tasks)
        self._logger.info("agent_initialized", agent_id=self.manifest.agent_id)

    async def shutdown(self) -> None:
        """Called by the runtime on graceful shutdown. Override to clean up resources."""
        self._logger.info("agent_shutdown", agent_id=self.manifest.agent_id)

    async def health_check(self) -> bool:
        """Return True if the agent is ready to accept tasks."""
        return True

    @abstractmethod
    async def execute(self, subtask: SubTask) -> AgentResult:
        """
        Core execution method. Must be implemented by every agent.

        Args:
            subtask: The SubTask unit of work, including input_data and context.

        Returns:
            AgentResult with output, timing, and tool call records.
        """

    async def run(self, subtask: SubTask) -> AgentResult:
        """
        Wraps execute() with timeout, semaphore, and structured telemetry.
        Called by the AgentRuntime — do not override unless necessary.
        """
        assert self._semaphore is not None, "Agent not initialized. Call initialize() first."
        start_ms = time.monotonic() * 1000

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    self.execute(subtask),
                    timeout=self.manifest.timeout_seconds,
                )
                result.execution_time_ms = time.monotonic() * 1000 - start_ms
                self._logger.info(
                    "agent_task_completed",
                    agent_id=self.manifest.agent_id,
                    subtask_id=subtask.subtask_id,
                    success=result.success,
                    duration_ms=round(result.execution_time_ms, 2),
                )
                return result
            except asyncio.TimeoutError:
                self._logger.error(
                    "agent_task_timeout",
                    agent_id=self.manifest.agent_id,
                    subtask_id=subtask.subtask_id,
                    timeout=self.manifest.timeout_seconds,
                )
                return AgentResult(
                    subtask_id=subtask.subtask_id,
                    agent_id=self.manifest.agent_id,
                    success=False,
                    error_message=f"Agent timed out after {self.manifest.timeout_seconds}s",
                    error_code="AGENT_TIMEOUT",
                    execution_time_ms=time.monotonic() * 1000 - start_ms,
                )
            except Exception as exc:
                self._logger.exception(
                    "agent_task_error",
                    agent_id=self.manifest.agent_id,
                    subtask_id=subtask.subtask_id,
                    error=str(exc),
                )
                return AgentResult(
                    subtask_id=subtask.subtask_id,
                    agent_id=self.manifest.agent_id,
                    success=False,
                    error_message=str(exc),
                    error_code="AGENT_EXEC_ERROR",
                    execution_time_ms=time.monotonic() * 1000 - start_ms,
                )

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a registered MCP-compatible tool.
        Subclasses override this to integrate actual tool backends.
        """
        raise NotImplementedError(f"Tool {tool_name!r} not implemented in {self.__class__.__name__}")
