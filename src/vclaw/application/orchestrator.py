"""Core orchestrator engine: intent classification, task decomposition, agent routing.

The orchestrator implements a state machine:
    PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED
                                                 → FAILED
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from opentelemetry import trace

from vclaw.agents.registry import AgentRegistry
from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.domain.models import (
    AgentRequest,
    IncomingMessage,
    IntentClassification,
    LLMRequest,
    SubTask,
    TaskStatus,
    WorkflowState,
)
from vclaw.infrastructure.event_bus.base import EventBus
from vclaw.infrastructure.llm.router import LLMRouter
from vclaw.infrastructure.persistence.state_store import StateStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class Orchestrator:
    """Central orchestration engine for the Vclaw platform.

    Responsibilities:
    - Classify user intent via LLM
    - Decompose complex tasks into subtasks
    - Route subtasks to appropriate agents
    - Manage workflow state machine transitions
    - Aggregate results and compose final response
    """

    def __init__(
        self,
        event_bus: EventBus,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        state_store: StateStore,
        max_retries: int = 3,
    ) -> None:
        self._event_bus = event_bus
        self._registry = agent_registry
        self._llm = llm_router
        self._state_store = state_store
        self._max_retries = max_retries

    async def setup(self) -> None:
        """Subscribe to relevant events on the bus."""
        await self._event_bus.subscribe(EventTypes.MESSAGE_NORMALIZED, self._handle_message)

    async def _handle_message(self, event: CloudEvent) -> None:
        """Entry point: process a normalized incoming message."""
        with tracer.start_as_current_span("orchestrator.handle_message"):
            message = IncomingMessage.model_validate(event.data)

            if await self._state_store.check_idempotency(message.idempotency_key):
                logger.info("duplicate_message_skipped", key=message.idempotency_key)
                return

            await self._state_store.mark_idempotency(message.idempotency_key)

            workflow = WorkflowState(
                message=message,
                tenant_id=event.tenant_id,
            )
            workflow.transition(TaskStatus.ROUTING)
            await self._state_store.save(workflow)

            try:
                intent = await self._classify_intent(message, workflow)
                workflow.intent = intent
                await self._state_store.save(workflow)

                await self._event_bus.publish(
                    CloudEvent(
                        type=EventTypes.INTENT_CLASSIFIED,
                        data=intent.model_dump(),
                        correlation_id=workflow.id,
                        tenant_id=workflow.tenant_id,
                    )
                )

                subtasks = await self._decompose_task(message, intent, workflow)
                workflow.subtasks = subtasks
                await self._state_store.save(workflow)

                await self._event_bus.publish(
                    CloudEvent(
                        type=EventTypes.TASK_DECOMPOSED,
                        data={
                            "workflow_id": workflow.id,
                            "subtask_count": len(subtasks),
                            "subtasks": [s.model_dump(mode="json") for s in subtasks],
                        },
                        correlation_id=workflow.id,
                        tenant_id=workflow.tenant_id,
                    )
                )

                workflow.transition(TaskStatus.EXECUTING)
                await self._state_store.save(workflow)
                await self._execute_subtasks(workflow)

                workflow.transition(TaskStatus.AGGREGATING)
                await self._state_store.save(workflow)
                result = await self._aggregate_results(workflow)

                workflow.result = result
                workflow.transition(TaskStatus.COMPLETED)
                await self._state_store.save(workflow)

                await self._event_bus.publish(
                    CloudEvent(
                        type=EventTypes.WORKFLOW_COMPLETED,
                        data={
                            "workflow_id": workflow.id,
                            "result": result,
                            "message": message.model_dump(mode="json"),
                        },
                        correlation_id=workflow.id,
                        tenant_id=workflow.tenant_id,
                    )
                )

            except Exception as exc:
                logger.exception("workflow_failed", workflow_id=workflow.id)
                workflow.error = str(exc)
                workflow.transition(TaskStatus.FAILED)
                await self._state_store.save(workflow)

                await self._event_bus.publish(
                    CloudEvent(
                        type=EventTypes.WORKFLOW_FAILED,
                        data={
                            "workflow_id": workflow.id,
                            "error": str(exc),
                            "message": message.model_dump(mode="json"),
                        },
                        correlation_id=workflow.id,
                        tenant_id=workflow.tenant_id,
                    )
                )

    async def _classify_intent(
        self, message: IncomingMessage, workflow: WorkflowState
    ) -> IntentClassification:
        """Use LLM to classify user intent and determine target agent."""
        with tracer.start_as_current_span("orchestrator.classify_intent"):
            available_agents = self._registry.agents
            agent_descriptions = []
            for name, agent in available_agents.items():
                caps = [f"  - {c.name}: {c.description}" for c in agent.manifest.capabilities]
                agent_descriptions.append(
                    f"Agent: {name}\n"
                    f"Description: {agent.manifest.description}\n"
                    f"Capabilities:\n" + "\n".join(caps)
                )

            agents_context = (
                "\n\n".join(agent_descriptions) if agent_descriptions else "No agents available."
            )

            system_prompt = (
                "You are the Vclaw intent classifier. Analyze the user message and determine:\n"
                "1. The intent (what the user wants to do)\n"
                "2. Which agent should handle it\n"
                "3. Extracted parameters\n\n"
                f"Available agents:\n{agents_context}\n\n"
                "Respond in JSON format:\n"
                '{"intent": "string", "confidence": float, "target_agent": "agent_name", '
                '"parameters": {}, "reasoning": "string"}'
            )

            request = LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message.text},
                ],
                temperature=0.0,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            response = await self._llm.complete(request)
            try:
                data = json.loads(response.content)
                return IntentClassification.model_validate(data)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning(
                    "intent_parse_fallback",
                    raw=response.content[:200],
                    error=str(exc),
                )
                return IntentClassification(
                    intent="unknown",
                    confidence=0.0,
                    target_agent="",
                    reasoning=f"Failed to parse: {response.content[:200]}",
                )

    async def _decompose_task(
        self,
        message: IncomingMessage,
        intent: IntentClassification,
        workflow: WorkflowState,
    ) -> list[SubTask]:
        """Decompose into subtasks. Simple intents produce a single subtask."""
        with tracer.start_as_current_span("orchestrator.decompose_task"):
            if intent.target_agent and self._registry.get(intent.target_agent):
                return [
                    SubTask(
                        agent_name=intent.target_agent,
                        input_data={
                            "text": message.text,
                            "intent": intent.intent,
                            **intent.parameters,
                        },
                    )
                ]

            agents_by_cap = self._registry.find_by_capability(intent.intent)
            if agents_by_cap:
                return [
                    SubTask(
                        agent_name=agents_by_cap[0].name,
                        input_data={
                            "text": message.text,
                            "intent": intent.intent,
                            **intent.parameters,
                        },
                    )
                ]

            system_prompt = (
                "You are a task decomposer. Break the user request into subtasks.\n"
                f"Available agents: {list(self._registry.agents.keys())}\n"
                'Respond in JSON: {"subtasks": [{"agent_name": "...", "input_data": {}}]}'
            )

            request = LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Intent: {intent.intent}\nMessage: {message.text}",
                    },
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            response = await self._llm.complete(request)
            try:
                data = json.loads(response.content)
                subtasks = []
                for st in data.get("subtasks", []):
                    agent_name = st.get("agent_name", "")
                    if self._registry.get(agent_name):
                        subtasks.append(
                            SubTask(
                                agent_name=agent_name,
                                input_data=st.get("input_data", {}),
                            )
                        )
                return (
                    subtasks
                    if subtasks
                    else [SubTask(agent_name="fallback", input_data={"text": message.text})]
                )
            except Exception:
                logger.exception("decomposition_failed")
                return [SubTask(agent_name="fallback", input_data={"text": message.text})]

    async def _execute_subtasks(self, workflow: WorkflowState) -> None:
        """Execute subtasks respecting dependency ordering."""
        with tracer.start_as_current_span("orchestrator.execute_subtasks"):
            completed_ids: set[str] = set()
            pending = list(workflow.subtasks)

            while pending:
                ready = [st for st in pending if all(dep in completed_ids for dep in st.depends_on)]
                if not ready:
                    failed_deps = [st.id for st in pending if st.status == TaskStatus.FAILED]
                    if failed_deps:
                        break
                    raise RuntimeError("Circular dependency or unresolvable subtasks")

                tasks = [self._execute_single_subtask(workflow, st) for st in ready]
                await asyncio.gather(*tasks, return_exceptions=True)

                for st in ready:
                    if st.status == TaskStatus.COMPLETED:
                        completed_ids.add(st.id)
                    pending.remove(st)

                await self._state_store.save(workflow)

    async def _execute_single_subtask(self, workflow: WorkflowState, subtask: SubTask) -> None:
        """Execute a single subtask with retry logic."""
        agent = self._registry.get(subtask.agent_name)
        if not agent:
            subtask.status = TaskStatus.FAILED
            subtask.error = f"Agent '{subtask.agent_name}' not found"
            return

        retry_policy = agent.manifest.retry_policy
        max_retries = retry_policy.max_retries if retry_policy else self._max_retries

        for attempt in range(max_retries + 1):
            subtask.status = TaskStatus.EXECUTING
            from vclaw.domain.models import _now

            subtask.started_at = _now()

            request = AgentRequest(
                workflow_id=workflow.id,
                subtask_id=subtask.id,
                agent_name=subtask.agent_name,
                input_data=subtask.input_data,
                context={"attempt": attempt, "tenant_id": workflow.tenant_id},
                tenant_id=workflow.tenant_id,
                timeout_seconds=agent.manifest.timeout_seconds,
                idempotency_key=f"{workflow.id}:{subtask.id}:{attempt}",
            )

            await self._event_bus.publish(
                CloudEvent(
                    type=EventTypes.AGENT_DISPATCHED,
                    data=request.model_dump(mode="json"),
                    correlation_id=workflow.id,
                    tenant_id=workflow.tenant_id,
                )
            )

            response = await agent.run(request)

            if response.success:
                subtask.status = TaskStatus.COMPLETED
                subtask.result = response.data
                subtask.completed_at = _now()

                await self._event_bus.publish(
                    CloudEvent(
                        type=EventTypes.AGENT_COMPLETED,
                        data=response.model_dump(mode="json"),
                        correlation_id=workflow.id,
                        tenant_id=workflow.tenant_id,
                    )
                )
                return

            logger.warning(
                "subtask_attempt_failed",
                agent=subtask.agent_name,
                attempt=attempt,
                error=response.error,
            )

            if attempt < max_retries:
                delay = min(
                    (retry_policy.base_delay_seconds if retry_policy else 1.0)
                    * ((retry_policy.exponential_base if retry_policy else 2.0) ** attempt),
                    (retry_policy.max_delay_seconds if retry_policy else 30.0),
                )
                await asyncio.sleep(delay)

        subtask.status = TaskStatus.FAILED
        subtask.error = response.error or "Max retries exceeded"

        await self._event_bus.publish(
            CloudEvent(
                type=EventTypes.AGENT_FAILED,
                data={
                    "workflow_id": workflow.id,
                    "subtask_id": subtask.id,
                    "agent_name": subtask.agent_name,
                    "error": subtask.error,
                },
                correlation_id=workflow.id,
                tenant_id=workflow.tenant_id,
            )
        )

    async def _aggregate_results(self, workflow: WorkflowState) -> dict[str, Any]:
        """Aggregate subtask results into a unified response."""
        with tracer.start_as_current_span("orchestrator.aggregate_results"):
            results: list[dict[str, Any]] = []
            errors: list[str] = []

            for st in workflow.subtasks:
                if st.status == TaskStatus.COMPLETED and st.result:
                    results.append(
                        {
                            "agent": st.agent_name,
                            "data": st.result,
                        }
                    )
                elif st.status == TaskStatus.FAILED:
                    errors.append(f"{st.agent_name}: {st.error}")

            if not results and errors:
                return {
                    "success": False,
                    "message": "All subtasks failed",
                    "errors": errors,
                }

            if len(results) == 1:
                return {
                    "success": True,
                    "data": results[0]["data"],
                    "agent": results[0]["agent"],
                    "errors": errors if errors else None,
                }

            combined_text_parts = []
            combined_data: dict[str, Any] = {}
            for r in results:
                agent_data = r["data"]
                combined_data[r["agent"]] = agent_data
                if "response_text" in agent_data:
                    combined_text_parts.append(agent_data["response_text"])

            return {
                "success": True,
                "data": combined_data,
                "response_text": "\n\n".join(combined_text_parts) if combined_text_parts else None,
                "errors": errors if errors else None,
            }
