# Domain Layer — `vclaw.domain`

This package is the **pure domain** of the Vclaw platform. It contains only Pydantic models and event definitions with **zero infrastructure dependencies** — no database, no HTTP, no I/O of any kind.

## Contents

| Module | Purpose |
|--------|---------|
| `models.py` | Core entities, value objects, and request/response contracts |
| `events.py` | CloudEvents v1.0 envelope and event-type registry |

---

## `models.py` — Core Domain Models

### Value Objects

| Class | Role |
|-------|------|
| `MessageSource` | Enum: `telegram`, `api`, `internal` — origin of an incoming message |
| `TaskStatus` | Workflow state machine states: `PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED / FAILED / TIMED_OUT / CANCELLED` |

### Agent Contract

| Class | Role |
|-------|------|
| `AgentCapability` | Declares one capability (name + description + JSON schemas) used for routing lookups |
| `ToolDefinition` | MCP-compatible tool schema; maps 1:1 to OpenAI function-calling format |
| `AgentManifest` | Full agent registration record: name, version, capabilities, tools, concurrency/timeout/retry settings |
| `RetryPolicy` | Exponential-backoff retry configuration attached to an `AgentManifest` |
| `AgentRequest` | Standardized **input** envelope passed to every `AgentBase.execute()` call |
| `AgentResponse` | Standardized **output** envelope returned from every `AgentBase.execute()` call |

### Orchestration Models

| Class | Role |
|-------|------|
| `IncomingMessage` | Normalized inbound message with auto-generated idempotency key (`source:chat_id:message_id`) |
| `IntentClassification` | LLM intent result: `intent`, `confidence`, `target_agent`, `parameters`, `reasoning` |
| `SubTask` | Decomposed unit of work within a workflow: agent assignment, input, status, dependency list |
| `WorkflowState` | Full execution state of one orchestration run; persisted to `StateStore` |

### LLM Contract

| Class | Role |
|-------|------|
| `LLMRequest` | Unified request to the LLM abstraction layer (messages, tools, temperature, etc.) |
| `LLMResponse` | Unified response: content, tool_calls, model, provider, usage, latency, cost |

---

## `events.py` — CloudEvents Definitions

All internal communication travels as **CloudEvents v1.0** envelopes.

### `CloudEvent` fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (ULID) | Auto-generated unique event ID |
| `type` | `str` | Event type string (see `EventTypes`) |
| `source` | `str` | Emitting component (`vclaw/orchestrator`, etc.) |
| `data` | `dict` | Arbitrary payload |
| `correlation_id` | `str` | Links events from the same workflow run |
| `tenant_id` | `str` | Multi-tenant context propagation |
| `timestamp` | `datetime` | UTC creation time |

### `EventTypes` registry

```
vclaw.message.received          — Raw message ingested by gateway
vclaw.message.normalized        — Message normalized to IncomingMessage schema
vclaw.intent.classified         — LLM intent classification completed
vclaw.task.decomposed           — Orchestrator subtask decomposition done
vclaw.agent.dispatched          — Subtask sent to an agent
vclaw.agent.completed           — Agent returned a successful result
vclaw.agent.failed              — Agent returned an error (all retries exhausted)
vclaw.workflow.completed        — Entire workflow finished successfully
vclaw.workflow.failed           — Entire workflow failed
vclaw.agent.registered          — Agent registered in the registry
vclaw.agent.deregistered        — Agent removed from the registry
```

---

## Design Principles

- **No side effects:** Domain models never import infrastructure code. Safe to unit-test without stubs.
- **Pydantic v2:** All models use `model_validate`, `model_dump(mode="json")`, and typed fields.
- **ULID IDs:** All IDs use `python-ulid` for sortable, URL-safe unique identifiers.
- **UTC timestamps:** All `datetime` fields use `datetime.now(UTC)` for timezone-aware values.

---

## Adding a New Domain Model

1. Define a Pydantic `BaseModel` subclass in `models.py`.
2. Use `Field(default_factory=...)` for mutable defaults.
3. Add it to the relevant `__init__.py` if re-exported.
4. Do **not** import anything from `vclaw.infrastructure` or `vclaw.application`.
