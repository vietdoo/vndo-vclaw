# Application Layer (`vclaw.application`)

Contains the orchestration engine — the core business logic that coordinates intent classification, task decomposition, agent routing, and result aggregation.

## Files

### `orchestrator.py` — Central Orchestration Engine

The `Orchestrator` class implements a **state machine workflow**:

```
PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED
                                              → FAILED
```

**Dependencies (injected via constructor):**
- `EventBus` — publish/subscribe to CloudEvents
- `AgentRegistry` — look up and dispatch to agents
- `LLMRouter` — classify intent and decompose tasks
- `StateStore` — persist workflow state and enforce idempotency

**Core Pipeline (`_handle_message`):**

1. **Idempotency check** — Reject duplicate messages via `StateStore.check_idempotency()`
2. **Intent classification** (`_classify_intent`) — LLM call with available agent descriptions as context. Falls back to `intent="unknown"` on parse failure.
3. **Task decomposition** (`_decompose_task`) — Single subtask if target agent is identified directly; LLM decomposition for complex multi-agent tasks.
4. **Subtask execution** (`_execute_subtasks`) — Respects `depends_on` dependency ordering. Independent subtasks run in parallel via `asyncio.gather`. Retries with exponential backoff per agent's `RetryPolicy`.
5. **Result aggregation** (`_aggregate_results`) — Single results pass through; multiple results are combined with per-agent data and merged `response_text`.

**Event Emissions:** The orchestrator publishes events at each stage — `INTENT_CLASSIFIED`, `TASK_DECOMPOSED`, `AGENT_DISPATCHED`, `AGENT_COMPLETED/FAILED`, `WORKFLOW_COMPLETED/FAILED`. All events carry `correlation_id` (= workflow ID) and `tenant_id` for tracing.

**Error Handling:** Any exception in the pipeline transitions workflow to `FAILED` and publishes `WORKFLOW_FAILED`.

## Integration Points

- **Subscribes to:** `EventTypes.MESSAGE_NORMALIZED`
- **Publishes:** `INTENT_CLASSIFIED`, `TASK_DECOMPOSED`, `AGENT_DISPATCHED`, `AGENT_COMPLETED`, `AGENT_FAILED`, `WORKFLOW_COMPLETED`, `WORKFLOW_FAILED`
- **Uses:** `AgentRegistry.get()`, `AgentRegistry.find_by_capability()`, `AgentBase.run()`, `LLMRouter.complete()`, `StateStore.save/get/check_idempotency`
