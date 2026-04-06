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
│  • Monitoring & stats REST API (/api/v1/*)                       │
└──────────────────────────┬───────────────────────────────────────┘
                           │ CloudEvent: message.normalized
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EVENT BUS (Pub/Sub)                            │
│  Backends: InMemory │ Redis Streams │ Apache Kafka               │
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
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   PERSISTENCE                                     │
│  • InMemory (dev/test)                                           │
│  • PostgreSQL (production): workflow state, idempotency,          │
│    system event log for audit/analytics                           │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingestion:** Telegram webhook → API Gateway → normalize → emit `message.normalized`
2. **Routing:** Orchestrator subscribes → LLM classifies intent → decomposes into subtasks
3. **Execution:** Subtasks dispatched to agents (parallel where possible, sequential for dependencies)
4. **Aggregation:** Results collected → composed into response → emit `workflow.completed`
5. **Delivery:** Response handler subscribes → sends Telegram reply
6. **Logging:** All events persisted to PostgreSQL for audit trail and real-time dashboard

### State Management & Idempotency

- **Workflow State Machine:** `PENDING → ROUTING → EXECUTING → AGGREGATING → COMPLETED/FAILED`
- **Idempotency:** Each message gets a deterministic key (`source:chat_id:message_id`); duplicates are rejected at the orchestrator layer
- **State Store:** Abstract interface with in-memory (dev) and PostgreSQL (production) implementations

### Multi-Tenant Context Propagation

- `tenant_id` flows through `CloudEvent` → `WorkflowState` → `AgentRequest`
- All logs and traces include tenant context via structlog contextvars
- Agent execution is tenant-isolated via the request context

---

## 2. Project Structure

```
vclaw/
├── pyproject.toml                    # Dependencies, entry points, tool config
├── Dockerfile                        # Multi-stage production container
├── docker-compose.yml                # Full stack: vclaw + Kafka + PostgreSQL + Redis
├── .dockerignore
├── .env.example                      # Environment variable template
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
│       │   │   ├── redis_streams.py # Redis Streams (production)
│       │   │   └── kafka_bus.py     # Apache Kafka (production, recommended)
│       │   ├── llm/
│       │   │   ├── base.py          # Abstract LLMProvider
│       │   │   ├── openai_compat.py # OpenAI-compatible provider
│       │   │   └── router.py        # Multi-provider fallback router
│       │   ├── persistence/
│       │   │   ├── state_store.py   # Abstract + InMemory state store
│       │   │   └── postgres_store.py # PostgreSQL: state + event log
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
│           ├── response_handler.py  # Event → Telegram reply bridge
│           └── monitoring.py        # REST API for dashboard/stats
│
├── tests/                            # Test suite (59 tests)
├── plugins/                          # Drop-in agent plugins
└── examples/
    └── plugin_agent/                # Example custom agent
```

---

## 3. Docker Deployment

### Quick Start with Docker Compose

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your Telegram bot token and LLM API keys

# 2. Start the full stack
docker compose up -d

# 3. Start with Kafka UI for debugging (dev profile)
docker compose --profile dev up -d

# 4. Check status
docker compose ps
docker compose logs -f vclaw
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `vclaw` | 8080 | Main application |
| `postgres` | 5432 | PostgreSQL 16 (state + event log) |
| `kafka` | 9092 | Apache Kafka (KRaft mode, no Zookeeper) |
| `redis` | 6379 | Redis 7 (caching) |
| `kafka-ui` | 8090 | Kafka UI (dev profile only) |

### Health Checks

All infrastructure services have Docker healthchecks. The `vclaw` container waits for all dependencies to be healthy before starting.

```bash
# Check application health
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

### Resource Limits

| Service | Memory Limit | CPU Limit |
|---------|-------------|-----------|
| vclaw | 512M | 1.0 |
| postgres | 256M | - |
| kafka | 1G | - |
| redis | 128M | - |

---

## 4. Monitoring & Stats API

REST API endpoints designed for building a real-time dashboard frontend.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/stats/system` | System overview: uptime, component health, agent status |
| `GET` | `/api/v1/stats/workflows` | Workflow execution statistics |
| `GET` | `/api/v1/stats/events/summary` | Event type counts (last 24h) |
| `GET` | `/api/v1/events` | Query system event log (paginated, filterable) |
| `GET` | `/api/v1/workflows/active` | List currently active workflows |
| `GET` | `/api/v1/workflows/{id}` | Workflow detail |
| `GET` | `/api/v1/agents/health` | Agent health + manifest info |

### Query Parameters

**`/api/v1/events`:**
- `event_type` — filter by event type (e.g., `vclaw.workflow.completed`)
- `correlation_id` — filter by workflow correlation ID
- `tenant_id` — filter by tenant
- `level` — filter by level (`info`, `error`)
- `since` / `until` — ISO datetime range
- `limit` (max 500) / `offset` — pagination

**`/api/v1/stats/workflows`:**
- `since` — ISO datetime or hours (e.g., `24` for last 24 hours)
- `tenant_id` — filter by tenant

### Example Responses

```bash
# System stats
curl http://localhost:8080/api/v1/stats/system
```

```json
{
  "status": "healthy",
  "uptime_seconds": 3621.4,
  "service": "vclaw",
  "timestamp": "2026-04-06T10:00:00+00:00",
  "components": {
    "event_bus": {"backend": "kafka", "status": "running"},
    "state_store": {"backend": "postgres", "status": "running"},
    "agents": {"count": 2, "names": ["task_management", "public_service"]},
    "llm_providers": {"openai": true}
  }
}
```

---

## 5. Event Bus: Kafka

The platform uses Apache Kafka as the production event bus (replacing the earlier NATS placeholder).

### Features

- **Topic-per-event-type:** Independent scaling per event stream
- **Consumer groups:** Horizontal scaling across multiple workers
- **Idempotent producer:** Exactly-once semantics with `enable_idempotence=True`
- **Gzip compression:** Reduced network bandwidth
- **Dead-letter queue:** Failed events routed to `vclaw.dlq` topic
- **Configurable partitions:** Default 3 partitions for parallelism

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VCLAW_EVENT_BUS_BACKEND` | `memory` | Set to `kafka` for production |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker addresses |
| `KAFKA_CONSUMER_GROUP` | `vclaw` | Consumer group ID |
| `KAFKA_TOPIC_PREFIX` | `vclaw.` | Topic name prefix |
| `KAFKA_AUTO_OFFSET_RESET` | `earliest` | Where to start consuming |
| `KAFKA_MAX_CONCURRENT` | `50` | Max parallel message processing |

---

## 6. PostgreSQL Persistence

### Schema

- **`workflow_states`** — Durable workflow state with JSONB columns for flexible data
- **`idempotency_keys`** — Deduplication tracking
- **`system_event_log`** — Full audit trail of all platform events (indexed by type, correlation, tenant, time)

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VCLAW_PERSISTENCE_BACKEND` | `memory` | Set to `postgres` for production |
| `POSTGRES_DSN` | `postgresql://vclaw:vclaw@localhost:5432/vclaw` | Connection string |
| `POSTGRES_MIN_POOL_SIZE` | `5` | Minimum connection pool size |
| `POSTGRES_MAX_POOL_SIZE` | `20` | Maximum connection pool size |
| `VCLAW_ENABLE_EVENT_LOGGING` | `true` | Enable event → PostgreSQL logging |

### Fault Tolerance

- If PostgreSQL is unreachable at startup, the platform gracefully falls back to in-memory state store
- Connection pooling via asyncpg for high throughput
- Auto-creates schema on first connection

---

## 7. Fault Tolerance & Resilience

### Load Handling

- **Event bus backpressure:** Configurable semaphore limits parallel handler execution
- **Per-agent concurrency:** Each agent's `max_concurrent` enforced via asyncio.Semaphore
- **Kafka partitioning:** Events distributed across partitions for parallel consumption
- **Connection pooling:** asyncpg pool (5-20 connections), httpx connection reuse

### Error Recovery

- **Retry policy:** Per-agent configurable retries with exponential backoff
- **Dead-letter queue:** Failed events routed to DLQ (Kafka topic or in-memory)
- **Circuit breaker:** LLM providers marked unhealthy on failure, skipped in routing
- **Graceful degradation:** Platform runs without LLM (agents use fallback logic)
- **Persistence fallback:** Postgres failure → automatic fallback to in-memory store

### Observability

- **Structured logging:** structlog with JSON output, tenant/workflow context propagation
- **Distributed tracing:** OpenTelemetry spans across orchestrator → agents → LLM calls
- **Health probes:** `/health` and `/ready` endpoints for Kubernetes/Docker healthchecks
- **Event audit log:** All platform events persisted to PostgreSQL `system_event_log`
- **Dashboard API:** 7 REST endpoints for real-time monitoring

---

## 8. Quick Start

### Local Development

```bash
# Install
pip install -e ".[dev]"

# Configure (minimal)
export TELEGRAM_BOT_TOKEN="your-bot-token"
export VCLAW_LLM_PROVIDERS='[{"name":"openai","api_key":"sk-...","model":"gpt-4o-mini"}]'

# Run (in-memory mode)
python -m vclaw.app

# Run tests
pytest tests/ -v
```

### Production (Docker)

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN, VCLAW_LLM_PROVIDERS, etc.

docker compose up -d
# Application at http://localhost:8080
# Dashboard API at http://localhost:8080/api/v1/stats/system
```

---

## 9. Configuration Reference

All settings via environment variables with `VCLAW_` prefix. See `src/vclaw/config.py` for the complete schema.

| Variable | Default | Description |
|----------|---------|-------------|
| `VCLAW_ENVIRONMENT` | `development` | Environment mode |
| `VCLAW_EVENT_BUS_BACKEND` | `memory` | Event bus: `memory`, `redis`, `kafka` |
| `VCLAW_PERSISTENCE_BACKEND` | `memory` | State store: `memory`, `postgres` |
| `VCLAW_MAX_CONCURRENT_AGENTS` | `10` | Global agent concurrency limit |
| `VCLAW_ENABLE_EVENT_LOGGING` | `true` | Log events to PostgreSQL |
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot API token |
| `TELEGRAM_WEBHOOK_URL` | - | Public webhook URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker addresses |
| `POSTGRES_DSN` | `postgresql://vclaw:vclaw@localhost:5432/vclaw` | PostgreSQL connection |

---

## 10. Agent SDK Guide

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
