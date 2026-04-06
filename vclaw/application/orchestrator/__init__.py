"""
Orchestrator Engine: intent classification, task decomposition,
routing strategy, workflow state machine, and result aggregation.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from pydantic import BaseModel

from vclaw.application.registry import AgentRegistry
from vclaw.domain.events.bus_events import CloudEvent, EventType
from vclaw.domain.exceptions import IntentClassificationError
from vclaw.domain.models.base import (
    AgentCapability,
    AgentResult,
    IncomingMessage,
    IntentClassification,
    OrchestratorTask,
    Priority,
    SubTask,
    TaskStatus,
    TenantContext,
)
from vclaw.infrastructure.eventbus import EventBus
from vclaw.infrastructure.llm import LLMMessage, LLMRouter
from vclaw.infrastructure.observability import get_tracer

logger = structlog.get_logger(__name__)
tracer = get_tracer("vclaw.orchestrator")


INTENT_CLASSIFICATION_SYSTEM = """You are an intent classification engine for the Vclaw platform.
Given a user message, identify the primary agent capability needed and any secondary ones.
Extract relevant named entities (tasks, dates, names, locations, etc.).
Determine if the request requires breaking into multiple subtasks.

Respond ONLY with valid JSON matching this schema:
{
  "primary_capability": "<one of: task_management|public_service|code_review|search|calendar|notification|analytics|general>",
  "confidence": <float 0.0-1.0>,
  "secondary_capabilities": ["<capability>", ...],
  "extracted_entities": {"key": "value"},
  "requires_decomposition": <bool>,
  "raw_intent": "<brief description>"
}"""

TASK_DECOMPOSITION_SYSTEM = """You are a task decomposition engine.
Break the user's request into independent or sequential subtasks.
Each subtask targets a specific agent capability.

Respond ONLY with valid JSON:
{
  "subtasks": [
    {
      "capability": "<capability>",
      "description": "<what this subtask does>",
      "input_data": {"key": "value"},
      "priority": "<low|normal|high|critical>",
      "depends_on_indices": [<int>, ...]
    }
  ]
}"""


class DecomposedTaskSchema(BaseModel):
    class SubTaskSpec(BaseModel):
        capability: str
        description: str
        input_data: dict[str, Any] = {}
        priority: str = "normal"
        depends_on_indices: list[int] = []

    subtasks: list[SubTaskSpec]


class Orchestrator:
    """
    Core workflow engine.

    State machine transitions:
      PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED
                                                   ↘ FAILED
                       ↗ (on agent failure + retries exhausted)

    Idempotency: task_id derived from idempotency_key prevents duplicate processing.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: EventBus,
        llm_router: LLMRouter,
        max_concurrent_tasks: int = 50,
        task_timeout: int = 120,
        idempotency_ttl: int = 86400,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._llm = llm_router
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_timeout = task_timeout
        self._idempotency_ttl = idempotency_ttl
        self._active_tasks: dict[str, OrchestratorTask] = {}
        self._idempotency_cache: dict[str, str] = {}

    async def handle_message(self, message: IncomingMessage) -> OrchestratorTask:
        """
        Entry point: normalize message → classify → decompose → route → aggregate.
        Returns the completed OrchestratorTask.
        """
        if existing_task_id := self._idempotency_cache.get(message.idempotency_key):
            existing = self._active_tasks.get(existing_task_id)
            if existing and existing.status == TaskStatus.COMPLETED:
                logger.info(
                    "idempotent_request_deduped",
                    key=message.idempotency_key,
                    task_id=existing_task_id,
                )
                return existing

        task = OrchestratorTask(
            idempotency_key=message.idempotency_key,
            tenant=message.tenant,
            original_message=message,
        )
        self._active_tasks[task.task_id] = task
        self._idempotency_cache[message.idempotency_key] = task.task_id

        log = logger.bind(
            task_id=task.task_id,
            tenant_id=message.tenant.tenant_id,
            trace_id=task.trace_id,
        )

        with tracer.start_as_current_span("orchestrator.handle_message") as span:
            span.set_attribute("task.id", task.task_id)
            span.set_attribute("tenant.id", message.tenant.tenant_id)

            try:
                async with self._semaphore:
                    await asyncio.wait_for(
                        self._execute_task_lifecycle(task, log),
                        timeout=self._task_timeout,
                    )
            except asyncio.TimeoutError:
                task.transition_to(TaskStatus.TIMEOUT)
                task.final_response = "Request timed out. Please try again."
                log.error("task_timeout", timeout=self._task_timeout)
            except Exception as exc:
                task.transition_to(TaskStatus.FAILED)
                task.final_response = "An internal error occurred. Please try again."
                log.exception("task_lifecycle_error", error=str(exc))

        await self._publish_task_event(task)
        return task

    async def _execute_task_lifecycle(
        self, task: OrchestratorTask, log: Any
    ) -> None:
        task.transition_to(TaskStatus.ROUTING)
        await self._publish_task_event(task)

        intent = await self._classify_intent(task.original_message.text)
        task.intent = intent
        log.info("intent_classified", capability=intent.primary_capability, confidence=intent.confidence)

        await self._emit(
            CloudEvent.create(
                EventType.TASK_INTENT_CLASSIFIED,
                data={"task_id": task.task_id, "intent": intent.model_dump()},
                subject=task.task_id,
                tenant_id=task.tenant.tenant_id,
                trace_id=task.trace_id,
            )
        )

        if intent.requires_decomposition:
            subtasks = await self._decompose_task(task)
        else:
            subtask = SubTask(
                parent_task_id=task.task_id,
                capability=intent.primary_capability,
                input_data={
                    "text": task.original_message.text,
                    "entities": intent.extracted_entities,
                    "tenant": task.tenant.model_dump(),
                },
            )
            subtasks = [subtask]

        task.subtasks = subtasks
        await self._emit(
            CloudEvent.create(
                EventType.TASK_DECOMPOSED,
                data={"task_id": task.task_id, "subtask_count": len(subtasks)},
                subject=task.task_id,
                tenant_id=task.tenant.tenant_id,
            )
        )

        task.transition_to(TaskStatus.EXECUTING)
        results = await self._execute_subtasks(subtasks, task.trace_id, log)
        task.results = results

        task.transition_to(TaskStatus.AGGREGATING)
        final_response = await self._aggregate_results(task, results, log)
        task.final_response = final_response
        task.transition_to(TaskStatus.COMPLETED)

    async def _classify_intent(self, text: str) -> IntentClassification:
        messages = [
            LLMMessage(role="system", content=INTENT_CLASSIFICATION_SYSTEM),
            LLMMessage(role="user", content=f"Classify this user request: {text}"),
        ]
        try:
            return await self._llm.complete_structured(
                messages=messages,
                output_model=IntentClassification,
            )
        except Exception as exc:
            raise IntentClassificationError(str(exc)) from exc

    async def _decompose_task(self, task: OrchestratorTask) -> list[SubTask]:
        messages = [
            LLMMessage(role="system", content=TASK_DECOMPOSITION_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Decompose this request into subtasks:\n"
                    f"User message: {task.original_message.text}\n"
                    f"Primary intent: {task.intent.primary_capability if task.intent else 'general'}\n"
                    f"Entities: {json.dumps(task.intent.extracted_entities if task.intent else {})}"
                ),
            ),
        ]
        try:
            decomposed = await self._llm.complete_structured(
                messages=messages,
                output_model=DecomposedTaskSchema,
            )
        except Exception as exc:
            logger.warning("decomposition_failed_fallback", error=str(exc))
            cap = task.intent.primary_capability if task.intent else AgentCapability.GENERAL
            return [
                SubTask(
                    parent_task_id=task.task_id,
                    capability=cap,
                    input_data={"text": task.original_message.text},
                )
            ]

        subtasks: list[SubTask] = []
        id_map: dict[int, str] = {}
        for idx, spec in enumerate(decomposed.subtasks):
            try:
                cap = AgentCapability(spec.capability)
            except ValueError:
                cap = AgentCapability.GENERAL
            priority = Priority(spec.priority) if spec.priority in Priority._value2member_map_ else Priority.NORMAL
            depends_on = [id_map[i] for i in spec.depends_on_indices if i in id_map]
            st = SubTask(
                parent_task_id=task.task_id,
                capability=cap,
                input_data={**spec.input_data, "description": spec.description},
                priority=priority,
                depends_on=depends_on,
            )
            id_map[idx] = st.subtask_id
            subtasks.append(st)
        return subtasks

    async def _execute_subtasks(
        self,
        subtasks: list[SubTask],
        trace_id: str,
        log: Any,
    ) -> list[AgentResult]:
        """
        Execute subtasks respecting dependency ordering.
        Independent subtasks run in parallel; dependent ones run sequentially.
        """
        completed_ids: set[str] = set()
        results: list[AgentResult] = []
        pending = list(subtasks)

        while pending:
            ready = [
                st for st in pending
                if all(dep in completed_ids for dep in st.depends_on)
            ]
            if not ready:
                log.error("circular_dependency_detected", pending=[s.subtask_id for s in pending])
                break

            batch_results = await asyncio.gather(
                *[self._execute_single_subtask(st, trace_id, log) for st in ready],
                return_exceptions=True,
            )
            for st, result in zip(ready, batch_results):
                pending.remove(st)
                if isinstance(result, BaseException):
                    results.append(
                        AgentResult(
                            subtask_id=st.subtask_id,
                            agent_id="orchestrator",
                            success=False,
                            error_message=str(result),
                        )
                    )
                else:
                    results.append(result)
                completed_ids.add(st.subtask_id)

        return results

    async def _execute_single_subtask(
        self, subtask: SubTask, trace_id: str, log: Any
    ) -> AgentResult:
        await self._emit(
            CloudEvent.create(
                EventType.AGENT_TASK_ASSIGNED,
                data={"subtask_id": subtask.subtask_id, "capability": subtask.capability},
                subject=subtask.parent_task_id,
                trace_id=trace_id,
            )
        )

        try:
            agent = self._registry.best_agent_for_capability(subtask.capability)
            subtask.agent_id = agent.manifest.agent_id
        except Exception:
            logger.warning(
                "no_agent_for_capability_using_general",
                capability=subtask.capability,
            )
            try:
                agent = self._registry.best_agent_for_capability(AgentCapability.GENERAL)
                subtask.agent_id = agent.manifest.agent_id
            except Exception as exc:
                return AgentResult(
                    subtask_id=subtask.subtask_id,
                    agent_id="none",
                    success=False,
                    error_message=f"No agent available: {exc}",
                    error_code="NO_AGENT",
                )

        result = await agent.run(subtask)

        event_type = EventType.AGENT_TASK_COMPLETED if result.success else EventType.AGENT_TASK_FAILED
        await self._emit(
            CloudEvent.create(
                event_type,
                data={"subtask_id": subtask.subtask_id, "agent_id": result.agent_id, "success": result.success},
                subject=subtask.parent_task_id,
                trace_id=trace_id,
            )
        )
        return result

    async def _aggregate_results(
        self, task: OrchestratorTask, results: list[AgentResult], log: Any
    ) -> str:
        """Synthesize subtask results into a user-facing Telegram reply."""
        if not results:
            return "Không có kết quả nào được trả về."

        all_success = all(r.success for r in results)
        if len(results) == 1:
            result = results[0]
            if result.success:
                return result.output.get("message", result.output.get("response", str(result.output)))
            return f"Lỗi: {result.error_message or 'Không xác định'}"

        # Multi-result aggregation
        messages = [
            LLMMessage(role="system", content=(
                "You are aggregating results from multiple agent executions into a single, "
                "coherent user-facing response in Vietnamese. Be concise and friendly."
            )),
            LLMMessage(
                role="user",
                content=(
                    f"Original request: {task.original_message.text}\n\n"
                    f"Results:\n"
                    + "\n".join(
                        f"- {'✅' if r.success else '❌'} {r.agent_id}: {json.dumps(r.output if r.success else {'error': r.error_message}, ensure_ascii=False)}"
                        for r in results
                    )
                ),
            ),
        ]
        try:
            response = await self._llm.complete(messages=messages, max_tokens=512)
            return response.content or "Đã hoàn thành."
        except Exception as exc:
            log.warning("aggregation_llm_failed", error=str(exc))
            success_count = sum(1 for r in results if r.success)
            return f"Hoàn thành {success_count}/{len(results)} tác vụ."

    async def _emit(self, event: CloudEvent) -> None:
        try:
            await self._event_bus.publish(event)
        except Exception as exc:
            logger.warning("event_publish_failed", event_type=event.type, error=str(exc))

    async def _publish_task_event(self, task: OrchestratorTask) -> None:
        event_type_map = {
            TaskStatus.ROUTING: EventType.TASK_ROUTING,
            TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
            TaskStatus.FAILED: EventType.TASK_FAILED,
            TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
            TaskStatus.TIMEOUT: EventType.TASK_TIMEOUT,
        }
        et = event_type_map.get(task.status)
        if et:
            await self._emit(
                CloudEvent.create(
                    et,
                    data={"task_id": task.task_id, "status": task.status},
                    subject=task.task_id,
                    tenant_id=task.tenant.tenant_id,
                    trace_id=task.trace_id,
                )
            )
