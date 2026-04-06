# Domain Layer (`vclaw.domain`)

Pure domain models and event definitions. This layer has **zero infrastructure dependencies** — it only depends on `pydantic` and standard library types.

## Files

### `models.py` — Core Entities & Value Objects

All data contracts used across the platform:

| Model | Purpose |
|-------|---------|
| `IncomingMessage` | Normalized inbound message from any source (Telegram, API, internal). Auto-generates `idempotency_key` as `source:chat_id:id`. |
| `IntentClassification` | LLM intent classification result with confidence score and target agent routing. |
| `SubTask` | A decomposed unit of work within an orchestration workflow, with dependency tracking (`depends_on`). |
| `WorkflowState` | Full state machine for orchestration: `PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED/FAILED`. Includes `transition()` for status changes. |
| `AgentRequest` | Standardized input contract for agent execution. Contains `workflow_id`, `subtask_id`, `input_data`, tenant context, and timeout. |
| `AgentResponse` | Standardized output contract from agents. Includes `success` flag, `data` dict, `error`, and `duration_ms` metrics. |
| `AgentManifest` | Agent registration metadata: capabilities, tools, concurrency limits, retry policy, schemas. |
| `AgentCapability` | Single capability declaration for routing lookups. |
| `ToolDefinition` | MCP-compatible tool definition for LLM function calling. |
| `RetryPolicy` | Configurable retry with exponential backoff (`base_delay`, `max_delay`, `exponential_base`). |
| `LLMRequest` / `LLMResponse` | Unified LLM abstraction DTOs supporting messages, tools, response format, and usage tracking. |

**Enums:** `MessageSource` (telegram/api/internal), `TaskStatus` (pending/routing/executing/aggregating/completed/failed/timed_out/cancelled).

**ID Generation:** Uses ULID (`python-ulid`) for time-sortable unique IDs.

### `events.py` — CloudEvents Definitions

| Class | Purpose |
|-------|---------|
| `CloudEvent` | CloudEvents v1.0 envelope with `specversion`, `type`, `source`, `data`, `tenant_id`, `correlation_id`. Auto-generates `correlation_id` from `id` if not set. |
| `EventTypes` | String constants for all event types (e.g., `vclaw.message.normalized`, `vclaw.workflow.completed`). |

**Event Flow:** `MESSAGE_RECEIVED → MESSAGE_NORMALIZED → INTENT_CLASSIFIED → TASK_DECOMPOSED → AGENT_DISPATCHED → AGENT_COMPLETED → WORKFLOW_COMPLETED`

## Key Design Decisions

- All models use **Pydantic v2** for runtime validation and JSON serialization (`model_dump(mode="json")`).
- `WorkflowState.transition()` auto-updates `updated_at` timestamp.
- `IncomingMessage.model_post_init()` auto-generates idempotency key if not set.
- Domain models are **immutable-first** — mutations only via explicit methods.
