"""Agent base class defining the standardized execution contract."""

from __future__ import annotations

import abc
import asyncio
import time
from typing import Any, ClassVar

import structlog
from opentelemetry import trace

from vclaw.domain.models import (
    AgentManifest,
    AgentRequest,
    AgentResponse,
    LLMRequest,
    LLMResponse,
    ToolDefinition,
)
from vclaw.infrastructure.llm.router import LLMRouter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class AgentBase(abc.ABC):
    """Base class for all Vclaw agents.

    Every agent must:
    1. Declare a manifest with capabilities and tool definitions
    2. Implement the `execute` method
    3. Optionally override lifecycle hooks (setup, teardown, health_check)

    The runtime wraps execution with timeout enforcement, error isolation,
    structured logging, and OpenTelemetry span creation.
    """

    manifest: ClassVar[AgentManifest]

    def __init__(self, llm_router: LLMRouter | None = None) -> None:
        self._llm_router = llm_router
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def tools(self) -> list[ToolDefinition]:
        return self.manifest.tools

    async def setup(self) -> None:
        """Lifecycle hook: called once when agent is registered."""
        max_c = self.manifest.max_concurrent
        self._semaphore = asyncio.Semaphore(max_c)

    async def teardown(self) -> None:
        """Lifecycle hook: called when agent is deregistered."""
        return

    async def health_check(self) -> bool:
        """Return True if the agent is healthy and ready to accept work."""
        return True

    async def run(self, request: AgentRequest) -> AgentResponse:
        """Entrypoint: wraps execute with timeout, concurrency, tracing."""
        with tracer.start_as_current_span(
            f"agent.{self.name}.run",
            attributes={
                "agent.name": self.name,
                "workflow.id": request.workflow_id,
                "subtask.id": request.subtask_id,
            },
        ):
            if self._semaphore:
                await self._semaphore.acquire()

            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self.execute(request),
                    timeout=request.timeout_seconds or self.manifest.timeout_seconds,
                )
                duration = (time.monotonic() - start) * 1000
                result.duration_ms = duration
                logger.info(
                    "agent_executed",
                    agent=self.name,
                    workflow_id=request.workflow_id,
                    success=result.success,
                    duration_ms=duration,
                )
                return result

            except TimeoutError:
                duration = (time.monotonic() - start) * 1000
                logger.error("agent_timeout", agent=self.name, duration_ms=duration)
                return AgentResponse(
                    workflow_id=request.workflow_id,
                    subtask_id=request.subtask_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Agent {self.name} timed out after {duration:.0f}ms",
                    duration_ms=duration,
                )

            except Exception as exc:
                duration = (time.monotonic() - start) * 1000
                logger.exception("agent_error", agent=self.name, duration_ms=duration)
                return AgentResponse(
                    workflow_id=request.workflow_id,
                    subtask_id=request.subtask_id,
                    agent_name=self.name,
                    success=False,
                    error=str(exc),
                    duration_ms=duration,
                )

            finally:
                if self._semaphore:
                    self._semaphore.release()

    @abc.abstractmethod
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Core agent logic. Implement this in concrete agents."""

    async def call_llm(self, request: LLMRequest) -> LLMResponse:
        """Convenience: route an LLM request through the shared router."""
        if not self._llm_router:
            raise RuntimeError(f"Agent {self.name} has no LLM router configured")
        return await self._llm_router.complete(request)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool schemas for LLM function calling."""
        schemas: list[dict[str, Any]] = []
        for tool in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": tool.required_params,
                        },
                    },
                }
            )
        return schemas
