# Vclaw — AI Agent Orchestration Platform

A production-ready, event-driven platform that routes Telegram commands to specialized, independently pluggable AI agents via a centralized orchestrator.

---

## Architecture Blueprint

```
┌──────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (FastAPI)                        │
│  Telegram Webhook/Polling │ Signature Verification │ Rate Limiting   │
│         Message Normalization → Idempotency Enforcement              │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ IncomingMessage (CloudEvent)
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR ENGINE                               │
│                                                                       │
│  ┌─────────────┐   ┌─────────────────┐   ┌──────────────────────┐   │
│  │   Intent    │   │   Task          │   │   Result             │   │
│  │ Classifier  │──▶│  Decomposer     │──▶│  Aggregator          │   │
│  │  (LLM)      │   │  (LLM)          │   │  (LLM synthesis)     │   │
│  └─────────────┘   └────────┬────────┘   └──────────────────────┘   │
│                             │ SubTask[]                               │
│              ┌──────────────┼──────────────┐                         │
│              ▼              ▼              ▼                         │
│         [SubTask A]    [SubTask B]    [SubTask C]                    │
│         (parallel)     (parallel)    (depends A)                     │
└──────────────────────────────────────────────────────────────────────┘
              │                                     ▲
              ▼                                     │
┌──────────────────────────────────────────────────────────────────────┐
│                    EVENT BUS (Redis Streams / In-Memory)              │
│  CloudEvents v1.0 schema │ DLQ │ Consumer Groups │ Backpressure      │
└──────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      AGENT REGISTRY                                   │
│  Dynamic Discovery │ Capability Index │ Health Checks │ Priority Sort │
│                                                                       │
│  ┌─────────────────────┐   ┌──────────────────────────────────────┐  │
│  │  TaskManagementAgent│   │  PublicServiceAgent                  │  │
│  │  ─ create_task      │   │  ─ lookup_procedure                  │  │
│  │  ─ list_tasks       │   │  ─ track_document                    │  │
│  │  ─ update_status    │   │  ─ get_announcements                 │  │
│  │  ─ assign_task      │   │  ─ calculate_fee                     │  │
│  └─────────────────────┘   └──────────────────────────────────────┘  │
│                                                                       │
│  [ + Any plugin agent discovered from vclaw/agents/ or entry_points] │
└──────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     LLM ABSTRACTION LAYER                             │
│  Provider priority chain: OpenRouter Free → Anthropic → OpenAI       │
│  Fallback on error │ Retry with backoff │ Structured output (Pydantic)│
└──────────────────────────────────────────────────────────────────────┘
```

### Data/Control Flow

1. **Ingestion**: Telegram update → `TelegramGateway` → HMAC verify → rate limit → normalize → `IncomingMessage`
2. **Dedup**: `Orchestrator` checks `idempotency_key` in cache; returns existing result if duplicate
3. **Intent**: LLM classifies `primary_capability` + `extracted_entities` → `IntentClassification`
4. **Decompose**: If `requires_decomposition=true`, LLM breaks into `SubTask[]` with dependency graph
5. **Route**: `AgentRegistry.best_agent_for_capability(cap)` → highest-priority healthy agent
6. **Execute**: Parallel subtasks run concurrently; dependent subtasks wait for prerequisites
7. **Aggregate**: Multiple results merged by LLM into single Vietnamese reply
8. **Respond**: Final text sent back to Telegram chat

### State Machine

```
PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED
                                              ↘ FAILED
                   ↗ (fallback to GENERAL)
             ↗ TIMEOUT (orchestrator-level)
```

### Idempotency Strategy

- Idempotency key derived from `tg:{update_id}:{message_id}` for Telegram, or caller-supplied for API
- In-memory `_idempotency_cache: dict[str, str]` maps key → `task_id`
- Production: replace with Redis `SET NX EX {ttl}` for distributed idempotency

---

## Production Folder Structure

```
vclaw/                              # Platform root (Clean Architecture)
├── domain/                         # Pure domain: no I/O, no frameworks
│   ├── models/base.py              # Value objects, entities (Pydantic v2)
│   ├── events/bus_events.py        # CloudEvents schema
│   └── exceptions/__init__.py      # Exception hierarchy
├── application/                    # Use cases: orchestrates domain + infra
│   ├── orchestrator/__init__.py    # Intent → decompose → route → aggregate
│   ├── registry/__init__.py        # Agent discovery, capability index
│   └── workflows/                  # (Extend: complex multi-step workflows)
├── infrastructure/                 # I/O adapters: external services
│   ├── eventbus/__init__.py        # Redis Streams + InMemory event bus
│   ├── llm/__init__.py             # OpenRouter, Anthropic, OpenAI providers
│   ├── telegram/__init__.py        # Bot client, webhook, rate limiter
│   ├── storage/                    # (Extend: PostgreSQL, Redis state store)
│   └── observability/__init__.py   # structlog + OpenTelemetry setup
├── agents/                         # Pluggable agent implementations
│   ├── _base/__init__.py           # AgentBase, AgentManifest, ToolDefinition
│   ├── task_management/__init__.py # Kanban task agent
│   └── public_service/__init__.py  # Vietnamese public services agent
├── api/__init__.py                 # FastAPI app: webhook, health, admin
└── config/__init__.py              # Pydantic Settings (12-Factor config)

sdk/
├── templates/my_custom_agent/      # Copy-paste template for new agents
└── AGENT_SDK_GUIDE.md              # Full SDK documentation

tests/
├── unit/domain/                    # Domain model tests
├── unit/application/               # Orchestrator, registry, agent tests
├── unit/infrastructure/            # EventBus, LLM, Telegram tests
└── integration/                    # Full-stack FastAPI tests

deploy/
├── docker/Dockerfile               # Multi-stage production image
├── docker/docker-compose.yml       # Local stack (Redis + vclaw + OTEL)
└── k8s/deployment.yaml             # Deployment, Service, HPA, PDB
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Redis 7+ (for production event bus; in-memory used in development)

### Installation

```bash
git clone https://github.com/your-org/vclaw.git
cd vclaw
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and LLM API keys

pip install -e ".[dev]"
```

### Run Development Server

```bash
ENVIRONMENT=development python3 main.py
```

The platform starts with:
- `InMemoryEventBus` (no Redis required)
- `MockLLMProvider` (no LLM API keys required)
- Long-polling Telegram (no public URL required)

### Run with Docker Compose

```bash
cd deploy/docker
cp ../../.env.example ../../.env
# Edit .env
docker compose up -d
```

### Run Tests

```bash
TELEGRAM_BOT_TOKEN=test:token ENVIRONMENT=development python3 -m pytest tests/ -v
```

---

## End-to-End Flow Walkthrough

**User sends**: `"Tạo task cho team backend"` via Telegram

| Step | Event | State | Detail |
|------|-------|-------|--------|
| 1 | `vclaw.message.received` | — | Telegram update_id=99, normalized to `IncomingMessage` |
| 2 | — | ROUTING | Orchestrator checks idempotency cache (miss) |
| 3 | `vclaw.task.created` | ROUTING | `OrchestratorTask` created with trace_id |
| 4 | LLM call | — | Intent classification → `{primary: "task_management", confidence: 0.97}` |
| 5 | `vclaw.task.intent_classified` | — | Intent stored on task |
| 6 | `vclaw.task.decomposed` | — | Single subtask (no decomposition needed) |
| 7 | `vclaw.agent.task_assigned` | EXECUTING | Registry routes to `task-management-v1` |
| 8 | LLM tool call | — | Agent calls `create_task(title="Task cho team backend")` |
| 9 | `vclaw.agent.task_completed` | — | `AgentResult(success=True, output={task_id: "ABC123"})` |
| 10 | `vclaw.task.completed` | AGGREGATING→COMPLETED | Response: `"Đã tạo task #ABC123: Task cho team backend"` |
| 11 | Telegram reply | — | Bot sends reply in same thread |

**Error boundaries**:
- LLM failure → fallback chain (OpenRouter → Anthropic → OpenAI → mock)
- Agent timeout → `AgentResult(success=False, error_code="AGENT_TIMEOUT")`
- No agent for capability → fall back to `GENERAL` capability agent
- All agents fail → graceful degradation message to user
- Orchestrator timeout → `TaskStatus.TIMEOUT`, user informed to retry
- Duplicate update → idempotency cache returns existing result

---

## Scaling & Resilience

### Horizontal Scaling

- **Stateless orchestrator**: All state lives in Redis Streams + idempotency cache
- **Partitioned streams**: Each `EventType` has its own Redis stream; consumer groups allow N replicas
- **K8s HPA**: CPU/memory-triggered autoscaling (2–20 replicas) with PodDisruptionBudget

### Concurrency Controls

- **Orchestrator semaphore**: `asyncio.Semaphore(max_concurrent_tasks=50)` per instance
- **Per-agent semaphore**: `asyncio.Semaphore(max_concurrent_tasks)` from manifest
- **Rate limiter**: Sliding window per `user_id`, configurable via env vars
- **Backpressure**: Redis `XADD MAXLEN ~10000` prevents unbounded stream growth

### Failure Handling

| Failure | Mitigation |
|---------|-----------|
| LLM provider down | Fallback chain with exponential backoff |
| Agent crash | Exception caught in `AgentBase.run()`, returns failure `AgentResult` |
| Agent timeout | `asyncio.wait_for` hard timeout, graceful `AgentResult` returned |
| All agents unavailable | Graceful degradation message to user |
| Redis down | `InMemoryEventBus` fallback in development; circuit breaker in production |
| Duplicate Telegram update | Idempotency cache prevents double-processing |
| DLQ overflow | Redis stream bounded at 5000 DLQ entries |
| K8s node failure | PodDisruptionBudget ensures minimum 2 replicas running |

### Observability Stack

- **Structured logging**: `structlog` JSON output with `trace_id`, `tenant_id`, `agent_id`
- **Distributed tracing**: OpenTelemetry spans across orchestrator and agents, W3C `traceparent` propagation
- **Metrics** (extend): `/metrics` endpoint via `prometheus-fastapi-instrumentator`
- **Alerting thresholds**: P95 latency > 5s, error rate > 1%, DLQ depth > 100

---

## Adding a New Agent (Zero Core Changes)

```bash
# 1. Copy template
cp -r sdk/templates/my_custom_agent vclaw/agents/my_agent

# 2. Edit vclaw/agents/my_agent/__init__.py
#    - Set manifest fields (agent_id, capabilities, tools)
#    - Implement execute()
#    - Keep agent_class = MyAgent at bottom

# 3. Validate
python3 scripts/validate_agent.py vclaw/agents/my_agent

# 4. Restart platform — agent is auto-discovered
```

See `sdk/AGENT_SDK_GUIDE.md` for full documentation.

---

## Environment Variables

See `.env.example` for the complete reference. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | required | Bot API token from @BotFather |
| `TELEGRAM_WEBHOOK_URL` | optional | Public HTTPS URL for webhook mode |
| `LLM_PROVIDER_PRIORITY` | `openrouter_free,anthropic,openai` | Cost-aware routing order |
| `ENVIRONMENT` | `development` | `development` uses in-memory bus + mock LLM |
| `REDIS_HOST` | `localhost` | Redis for production event bus |
| `AGENT_PLUGIN_DIRS` | `vclaw/agents` | Comma-separated plugin scan paths |

---

## Production Pitfalls & Mitigations

| Pitfall | Design Mitigation |
|---------|------------------|
| Telegram duplicate updates | Idempotency key from `update_id:message_id` |
| Race condition on parallel subtasks | `asyncio.gather` + dependency DAG ordering |
| LLM hallucinating tool arguments | Pydantic v2 strict validation on all tool schemas |
| Agent holding semaphore forever | `asyncio.wait_for` hard timeout per agent |
| Redis stream growing unbounded | `XADD MAXLEN ~10000` + `XLEN` monitoring |
| Shared state across tenants | `TenantContext` propagated through every call |
| Graceful shutdown race | `preStop` hook + `terminationGracePeriodSeconds: 30` |
| CAP theorem: prefer availability | Event bus at-least-once delivery + idempotent handlers |
