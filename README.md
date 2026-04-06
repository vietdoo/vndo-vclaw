# Vclaw AI Agent Orchestration Platform

Production-ready, scalable AI agent platform that routes Telegram commands to specialized, independently pluggable AI agents via a centralized orchestrator.

---

## 1. Architecture Blueprint

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        TELEGRAM USERS                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Webhook / Polling
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (Starlette)                     │
│  • Webhook signature verification                                │
│  • Rate limiting (sliding window)                                │
│  • Message normalization                                         │
│  • Idempotency key extraction                                    │
│  • Health / readiness probes                                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ CloudEvent: message.normalized
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EVENT BUS (Pub/Sub)                            │
│  Backends: InMemory │ Redis Streams │ NATS (planned)             │
│  • At-least-once delivery                                        │
│  • Dead-letter queue                                             │
│  • Backpressure via semaphores                                   │
│  • CloudEvents v1.0 envelope                                     │
└────────┬──────────────┬───────────────┬──────────────────────────┘
         │              │               │
         ▼              ▼               ▼
┌────────────┐  ┌──────────────┐  ┌────────────────┐
│ ORCHESTRATOR│  │RESPONSE HANDLER│ │ DLQ HANDLER   │
│  Engine     │  │(Telegram reply)│  │(Error recovery)│
└──────┬─────┘  └──────────────┘  └────────────────┘
       │
       │ 1. Intent Classification (LLM)
       │ 2. Task Decomposition (LLM)
       │ 3. Agent Routing
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                      AGENT REGISTRY                              │
│  • Plugin discovery (entry points + directory scanning)           │
│  • Capability indexing (O(1) lookup)                             │
│  • Health checks                                                 │
│  • Lifecycle management (setup → run → teardown)                 │
├──────────────────┬───────────────────┬───────────────────────────┤
│  TaskManagement  │  PublicService     │  [Your Agent Here]       │
│  Agent           │  Agent             │                          │
│  • create_task   │  • lookup_service  │  • Implement AgentBase   │
│  • move_task     │  • submit_app      │  • Define manifest       │
│  • list_tasks    │  • check_status    │  • Drop in plugins/      │
└──────────────────┴───────────────────┴───────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   LLM ROUTER                                     │
│  • Priority-based provider fallback                              │
│  • Cost-aware routing                                            │
│  • OpenAI-compatible API (OpenAI, OpenRouter, Ollama, vLLM)      │
│  • Health monitoring per provider                                │
│  • Structured tool-calling schema enforcement                    │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingestion:** Telegram webhook → API Gateway → normalize → emit `message.normalized`
2. **Routing:** Orchestrator subscribes → LLM classifies intent → decomposes into subtasks
3. **Execution:** Subtasks dispatched to agents (parallel where possible, sequential for dependencies)
4. **Aggregation:** Results collected → composed into response → emit `workflow.completed`
5. **Delivery:** Response handler subscribes → sends Telegram reply

### State Management & Idempotency

- **Workflow State Machine:** `PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED/FAILED`
- **Idempotency:** Each message gets a deterministic key (`source:chat_id:message_id`); duplicates are rejected at the orchestrator layer
- **State Store:** Abstract interface with in-memory (dev) and Redis (production) implementations

### Multi-Tenant Context Propagation

- `tenant_id` flows through `CloudEvent` → `WorkflowState` → `AgentRequest`
- All logs and traces include tenant context via structlog contextvars
- Agent execution is tenant-isolated via the request context

---

## 2. Project Structure

```
vclaw/
├── pyproject.toml                    # Dependencies, entry points, tool config
├── README.md
├── src/
│   └── vclaw/
│       ├── __init__.py
│       ├── config.py                 # pydantic-settings configuration
│       ├── app.py                    # Platform bootstrap & lifecycle
│       │
│       ├── domain/                   # Domain Layer (pure models)
│       │   ├── models.py            # Core entities, value objects
│       │   └── events.py            # CloudEvents definitions
│       │
│       ├── application/              # Application Layer (use cases)
│       │   └── orchestrator.py      # Intent → decompose → route → aggregate
│       │
│       ├── infrastructure/           # Infrastructure Layer
│       │   ├── event_bus/
│       │   │   ├── base.py          # Abstract EventBus interface
│       │   │   ├── memory.py        # In-memory (dev/test)
│       │   │   └── redis_streams.py # Redis Streams (production)
│       │   ├── llm/
│       │   │   ├── base.py          # Abstract LLMProvider
│       │   │   ├── openai_compat.py # OpenAI-compatible provider
│       │   │   └── router.py        # Multi-provider fallback router
│       │   ├── persistence/
│       │   │   └── state_store.py   # Workflow state + idempotency
│       │   ├── observability/
│       │   │   ├── logging.py       # structlog setup
│       │   │   └── tracing.py       # OpenTelemetry setup
│       │   └── telegram/
│       │       ├── gateway.py       # Webhook + message handling
│       │       └── rate_limiter.py  # Sliding-window rate limiter
│       │
│       ├── agents/                   # Agent Subsystem
│       │   ├── base.py              # AgentBase abstract class
│       │   ├── registry.py          # Discovery, lifecycle, indexing
│       │   └── builtin/
│       │       ├── task_management/  # Kanban task agent
│       │       └── public_service/   # Government API agent
│       │
│       └── api/                      # API Layer
│           ├── webhook.py           # Starlette HTTP endpoints
│           └── response_handler.py  # Event → Telegram reply bridge
│
├── tests/                            # Test suite
├── plugins/                          # Drop-in agent plugins
└── examples/
    └── plugin_agent/                # Example custom agent
```

---

## 3. Core Implementation

See the source code in `src/vclaw/` for complete, type-annotated implementations of:

- **`EventBus`** (`infrastructure/event_bus/base.py`): Abstract async pub/sub with DLQ support
- **`InMemoryEventBus`** (`infrastructure/event_bus/memory.py`): Backpressure-controlled in-memory bus
- **`RedisStreamsEventBus`** (`infrastructure/event_bus/redis_streams.py`): Production bus with consumer groups
- **`AgentBase`** (`agents/base.py`): Execution contract with timeout, tracing, concurrency control
- **`AgentRegistry`** (`agents/registry.py`): Plugin discovery via entry points + directory scanning
- **`Orchestrator`** (`application/orchestrator.py`): Intent classification → decomposition → routing → aggregation
- **`LLMRouter`** (`infrastructure/llm/router.py`): Provider fallback chain with health tracking

---

## 4. Telegram Integration Pipeline

The pipeline handles:

1. **Webhook Setup:** Auto-registers webhook URL with Telegram on startup
2. **Signature Verification:** HMAC-SHA256 validation of `X-Telegram-Bot-Api-Secret-Token`
3. **Message Normalization:** Raw Telegram Update → `IncomingMessage` with unified schema
4. **Event Emission:** `MESSAGE_RECEIVED` → `MESSAGE_NORMALIZED` events on the bus
5. **Rate Limiting:** Per-chat sliding-window limiter (configurable via `TELEGRAM_RATE_LIMIT_*`)
6. **Response Delivery:** `ResponseHandler` subscribes to workflow events → sends Telegram messages

---

## 5. Example Agents

### TaskManagementAgent

Kanban task board with MCP-compatible tool definitions:
- `create_task`, `update_task`, `move_task`, `list_tasks`, `get_task`, `delete_task`
- LLM tool-calling for natural language → structured operation
- Fallback parsing when LLM is unavailable

### PublicServiceAgent

Vietnamese government service directory:
- `lookup_service`, `list_services`, `submit_application`, `check_status`
- Pre-loaded service data (CCCD, Passport, Business License, Land Certificate)
- Bilingual responses (Vietnamese/English)

---

## 6. Agent SDK Guide

### Creating a New Agent

**Step 1:** Create a new directory in `plugins/` or `src/vclaw/agents/builtin/`:

```python
from vclaw.agents.base import AgentBase
from vclaw.domain.models import (
    AgentCapability, AgentManifest, AgentRequest,
    AgentResponse, ToolDefinition,
)
from typing import ClassVar

class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        version="0.1.0",
        description="What this agent does",
        capabilities=[
            AgentCapability(
                name="my_capability",
                description="Detailed capability description",
            ),
        ],
        tools=[
            ToolDefinition(
                name="my_tool",
                description="What the tool does",
                parameters={"param1": {"type": "string"}},
                required_params=["param1"],
            ),
        ],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        text = request.input_data.get("text", "")
        # Your logic here
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": f"Processed: {text}"},
        )
```

**Step 2:** Registration (choose one):
- **Drop-in:** Place in `plugins/` directory → auto-discovered on startup
- **Entry point:** Add to `pyproject.toml`:
  ```toml
  [project.entry-points."vclaw.agents"]
  my_agent = "my_package:MyAgent"
  ```
- **Manual:** Call `await registry.register(MyAgent())`

**Step 3:** Test locally:

```python
import asyncio
from vclaw.domain.models import AgentRequest

agent = MyAgent()
asyncio.run(agent.setup())

request = AgentRequest(
    workflow_id="test", subtask_id="test",
    agent_name="my_agent", input_data={"text": "hello"},
)
response = asyncio.run(agent.run(request))
print(response.data)
```

### Manifest Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique agent identifier |
| `version` | `str` | No | Semver version |
| `description` | `str` | No | Human-readable description |
| `capabilities` | `list[AgentCapability]` | No | Capability declarations for routing |
| `tools` | `list[ToolDefinition]` | No | MCP-compatible tool schemas |
| `input_schema` | `dict` | No | JSON Schema for input validation |
| `output_schema` | `dict` | No | JSON Schema for output validation |
| `max_concurrent` | `int` | No | Concurrency limit (default: 5) |
| `timeout_seconds` | `float` | No | Execution timeout (default: 60) |
| `retry_policy` | `RetryPolicy` | No | Retry configuration |

---

## 7. End-to-End Flow Walkthrough

**Input:** User sends `"Tạo task cho team backend"` in Telegram

```
1. INGESTION
   Telegram → POST /webhook/telegram
   → verify_webhook_signature()
   → normalize_update() → IncomingMessage{text="Tạo task cho team backend", chat_id="123"}
   → rate_limiter.allow("123") → True
   → EventBus.publish(CloudEvent{type="vclaw.message.normalized", data=message})

2. ORCHESTRATOR PICKUP
   → Orchestrator._handle_message(event)
   → state_store.check_idempotency("telegram:123:msg-id") → False (new message)
   → WorkflowState created, status → ROUTING

3. INTENT CLASSIFICATION
   → LLM request with agent descriptions as context
   → LLM responds: {"intent": "task_creation", "target_agent": "task_management",
                     "parameters": {"team": "backend"}, "confidence": 0.95}
   → EventBus.publish(CloudEvent{type="vclaw.intent.classified"})

4. TASK DECOMPOSITION
   → Single target agent identified → 1 SubTask
   → SubTask{agent_name="task_management", input_data={text: "...", team: "backend"}}
   → EventBus.publish(CloudEvent{type="vclaw.task.decomposed"})

5. AGENT EXECUTION
   → WorkflowState status → EXECUTING
   → EventBus.publish(CloudEvent{type="vclaw.agent.dispatched"})
   → TaskManagementAgent.run(AgentRequest{...})
   → LLM tool-calling → create_task(title="Tạo task cho team backend", team="backend")
   → TaskStore.create_task() → TASK-0001
   → AgentResponse{success=True, data={response_text: "✅ Created TASK-0001: ..."}}
   → EventBus.publish(CloudEvent{type="vclaw.agent.completed"})

6. AGGREGATION
   → WorkflowState status → AGGREGATING
   → Single result → pass through
   → WorkflowState status → COMPLETED, result = {success: True, data: {...}}
   → EventBus.publish(CloudEvent{type="vclaw.workflow.completed"})

7. RESPONSE DELIVERY
   → ResponseHandler._on_completed(event)
   → TelegramGateway.send_message("123", "✅ Created TASK-0001: Tạo task cho team backend")
   → User sees response in Telegram
```

**Error boundaries:** Each stage has try/catch → on failure, workflow transitions to FAILED → error response sent to user.

---

## 8. Scaling & Resilience Strategy

### Horizontal Scaling

- **Stateless orchestrator:** All state in external store (Redis/DB), any instance can process any message
- **Event bus partitioning:** Redis Streams consumer groups distribute load across workers
- **Agent isolation:** Each agent runs with its own concurrency semaphore; a slow agent doesn't block others

### Concurrency Control

- **Event bus:** Configurable `max_concurrent` semaphore limits parallel handler execution
- **Agent runtime:** Per-agent `max_concurrent` from manifest, enforced via asyncio.Semaphore
- **HTTP client:** Connection pooling via httpx.AsyncClient (reused per provider)

### Failure Handling

- **Retry policy:** Per-agent configurable retries with exponential backoff
- **Dead-letter queue:** Failed events routed to DLQ stream for investigation
- **Circuit breaker:** LLM providers marked unhealthy on failure, skipped in routing
- **Fallback agents:** Built-in agents have keyword-based fallback when LLM is unavailable
- **Graceful degradation:** Platform runs without LLM providers (agents use fallback logic)

### Observability

- **Structured logging:** structlog with JSON output, tenant/workflow context propagation
- **Distributed tracing:** OpenTelemetry spans across orchestrator → agents → LLM calls
- **Health probes:** `/health` and `/ready` endpoints for Kubernetes liveness/readiness

---

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure (minimal)
export TELEGRAM_BOT_TOKEN="your-bot-token"
export VCLAW_LLM_PROVIDERS='[{"name":"openai","api_key":"sk-...","model":"gpt-4o-mini"}]'

# Run
python -m vclaw.app

# Run tests
pytest tests/ -v
```

## Configuration

All settings via environment variables with `VCLAW_` prefix. See `src/vclaw/config.py` for the complete schema.

| Variable | Default | Description |
|----------|---------|-------------|
| `VCLAW_ENVIRONMENT` | `development` | Environment mode |
| `VCLAW_EVENT_BUS_BACKEND` | `memory` | Event bus: `memory`, `redis`, `nats` |
| `VCLAW_MAX_CONCURRENT_AGENTS` | `10` | Global agent concurrency limit |
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot API token |
| `TELEGRAM_WEBHOOK_URL` | - | Public webhook URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
