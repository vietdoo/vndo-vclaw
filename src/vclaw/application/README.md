# Application Layer — `vclaw.application`

This package contains the **orchestration engine** — the central use-case coordinator that connects incoming messages to agents via LLM-driven routing.

## Contents

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | `Orchestrator` — intent classification, task decomposition, agent dispatch, result aggregation |

---

## `Orchestrator` — Workflow State Machine

The orchestrator subscribes to the event bus and implements the full lifecycle of every agent workflow:

```
PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED
                                             → FAILED
```

### Constructor

```python
Orchestrator(
    event_bus: EventBus,
    agent_registry: AgentRegistry,
    llm_router: LLMRouter,
    state_store: StateStore,
    max_retries: int = 3,
)
```

### Internal Stages

#### 1. `_classify_intent(message, workflow) → IntentClassification`

Calls the LLM with:
- A system prompt listing all registered agents and their capabilities.
- The raw user message as the user turn.

Expected JSON response:
```json
{
  "intent": "task_creation",
  "confidence": 0.95,
  "target_agent": "task_management",
  "parameters": {"team": "backend"},
  "reasoning": "User wants to create a task"
}
```

Falls back to `IntentClassification(intent="unknown", confidence=0.0)` on parse failure.

#### 2. `_decompose_task(message, intent, workflow) → list[SubTask]`

Fast path (no extra LLM call):
- If `intent.target_agent` maps to a registered agent → single `SubTask`.
- If `intent.intent` matches a capability name → single `SubTask` for the first match.

Slow path (LLM decomposition):
- Asks LLM to break the request into named subtasks with `agent_name` + `input_data` per subtask.
- Falls back to a single `fallback` subtask on parse errors.

#### 3. `_execute_subtasks(workflow)`

- Respects `SubTask.depends_on` for DAG-style sequential/parallel execution.
- Subtasks whose dependencies are all `COMPLETED` are dispatched concurrently via `asyncio.gather`.
- Calls `_execute_single_subtask` which wraps `agent.run()` with retry logic (per-agent `RetryPolicy`).

#### 4. `_aggregate_results(workflow) → dict`

- Collects `SubTask.result` from all `COMPLETED` subtasks.
- Single result: passes through directly (`data`, `agent`, optional `errors`).
- Multiple results: merges into `combined_data` keyed by agent name; concatenates `response_text` fields.

---

## Event Bus Integration

The orchestrator is purely **event-driven**:

| Trigger (subscribes to) | Emits |
|------------------------|-------|
| `vclaw.message.normalized` | `vclaw.intent.classified` |
| — | `vclaw.task.decomposed` |
| — | `vclaw.agent.dispatched` (per subtask) |
| — | `vclaw.agent.completed` / `vclaw.agent.failed` |
| — | `vclaw.workflow.completed` / `vclaw.workflow.failed` |

All events carry `correlation_id = workflow.id` and `tenant_id` for end-to-end traceability.

---

## Idempotency

Each `IncomingMessage` carries an `idempotency_key` (`source:chat_id:message_id`). The orchestrator:

1. Calls `state_store.check_idempotency(key)` before processing.
2. If duplicate → logs and returns immediately.
3. If new → calls `state_store.mark_idempotency(key)` before creating the `WorkflowState`.

---

## State Persistence

Every state transition calls `state_store.save(workflow)`:

```
PENDING  → created
ROUTING  → after idempotency check
           (intent saved after classification)
           (subtasks saved after decomposition)
EXECUTING → before dispatch
AGGREGATING → after all subtasks finish
COMPLETED / FAILED → final state + result/error
```

---

## Multi-tenancy

`tenant_id` is extracted from the incoming `CloudEvent.tenant_id` field and flows through:
- `WorkflowState.tenant_id`
- `AgentRequest.tenant_id`
- All emitted `CloudEvent.tenant_id`

Agents can use `request.tenant_id` to implement per-tenant data isolation.

---

## Extending the Orchestrator

To change routing strategy or add pre/post hooks:

1. Subclass `Orchestrator` and override `_classify_intent` or `_decompose_task`.
2. Or inject a custom `LLMRouter` with a different routing strategy.
3. To add middleware (e.g., audit logging), subscribe additional handlers on the event bus for the relevant event types.

---

## Observability

Every public method has an OpenTelemetry span:

| Span name | Attributes |
|-----------|-----------|
| `orchestrator.handle_message` | — |
| `orchestrator.classify_intent` | — |
| `orchestrator.decompose_task` | — |
| `orchestrator.execute_subtasks` | — |
| `orchestrator.aggregate_results` | — |

All structlog log lines include `workflow_id`, `agent`, and error context.
