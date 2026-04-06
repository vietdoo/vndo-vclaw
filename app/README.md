# Monitoring & Logging API — `app/`

This is a **separate FastAPI service** that provides a REST + WebSocket interface for observability, log management, and real-time workflow monitoring. It runs independently from the core Vclaw agent platform (`src/vclaw/`).

> **Docker service name:** `api` — runs on port **8000** via `uvicorn app.main:app`.

---

## Architecture

```
app/
├── main.py               # FastAPI app, lifespan hooks, middleware
├── core/
│   ├── config.py         # Pydantic-settings config (reads .env)
│   ├── logging.py        # structlog setup for API service
│   └── metrics.py        # Prometheus metrics definitions
├── db/
│   └── base.py           # SQLAlchemy async engine, SessionLocal factory
├── models/               # SQLAlchemy ORM models (PostgreSQL)
│   ├── log.py            # SystemLog — structured log entries
│   ├── event.py          # WorkflowEvent — workflow lifecycle records
│   └── metric.py         # SystemMetric — time-series metrics
├── schemas/              # Pydantic request/response schemas
│   ├── common.py         # PaginatedResponse, ErrorResponse
│   ├── event.py          # WorkflowEventCreate, WorkflowEventUpdate, etc.
│   ├── log.py            # SystemLogCreate, SystemLogRead, LogFilter
│   └── stats.py          # SystemStats, DashboardStats
├── api/
│   ├── middleware.py     # RequestID, CORS, timing middleware
│   └── routes/
│       ├── health.py     # /health, /live, /ready, /metrics
│       ├── logs.py       # CRUD + stats for SystemLog
│       ├── events.py     # CRUD + stats for WorkflowEvent
│       ├── metrics.py    # System metrics endpoint
│       ├── stats.py      # Dashboard stats snapshot
│       └── ws.py         # WebSocket: /ws/system and /ws/events
├── kafka/
│   ├── producer.py       # aiokafka producer (workflow events + system logs)
│   └── consumer.py       # aiokafka consumer (writes to Postgres)
└── services/
    ├── event_service.py  # DB CRUD for WorkflowEvent
    ├── log_service.py    # DB CRUD for SystemLog
    ├── redis_service.py  # Redis pub/sub for WebSocket fan-out
    └── stats_service.py  # System resource stats (psutil)
```

---

## Data Flow

```
vclaw agent platform
        │ (Kafka producer)
        ▼
  Kafka topics:
  ├── workflow-events    ──► Kafka consumer → WorkflowEvent table (Postgres)
  └── system-logs        ──► Kafka consumer → SystemLog table (Postgres)

REST clients / dashboards
        │
        ▼
  FastAPI routes
  ├── GET /api/v1/events      → query Postgres
  ├── GET /api/v1/logs        → query Postgres
  ├── GET /api/v1/stats/...   → Redis cache + psutil
  └── WebSocket /ws/events    → Redis pub/sub fan-out
```

---

## REST API Reference

### Health & Metrics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Full dependency check (Postgres, Redis, Kafka) |
| GET | `/live` | Liveness probe (always 200 if process is alive) |
| GET | `/ready` | Readiness probe (200 only when DB + Redis connected) |
| GET | `/metrics` | Prometheus text format metrics |

### Workflow Events — `/api/v1/events`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/events` | Create a workflow event record |
| GET | `/api/v1/events` | List events (paginated; filter by status, type, tenant) |
| GET | `/api/v1/events/{id}` | Get single event by ID |
| PATCH | `/api/v1/events/{id}` | Update status or result |
| GET | `/api/v1/events/stats/summary` | Aggregated workflow statistics |

### System Logs — `/api/v1/logs`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/logs` | Ingest a log entry |
| GET | `/api/v1/logs` | List logs (paginated; filter by level, source, time range) |
| GET | `/api/v1/logs/stats` | Log volume statistics |

### Stats — `/api/v1/stats`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stats/system` | CPU %, memory %, disk usage (psutil) |
| GET | `/api/v1/stats/dashboard` | Combined snapshot cached for 10 seconds |

### WebSocket — Real-time

| Path | Protocol | Description |
|------|----------|-------------|
| `/ws/system` | WS | System stats pushed every 2 seconds |
| `/ws/events` | WS | New workflow events via Redis pub/sub |

---

## Database Schema (PostgreSQL)

Managed by **Alembic** migrations in `migrations/`.

### `system_logs`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `level` | VARCHAR | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `message` | TEXT | |
| `source` | VARCHAR | emitting component |
| `context` | JSONB | arbitrary structured data |
| `timestamp` | TIMESTAMPTZ | |

### `workflow_events`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `workflow_id` | VARCHAR | correlates to `WorkflowState.id` |
| `event_type` | VARCHAR | `vclaw.workflow.*` event type string |
| `status` | VARCHAR | workflow `TaskStatus` |
| `tenant_id` | VARCHAR | |
| `payload` | JSONB | full event data |
| `result` | JSONB | final workflow result |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `system_metrics`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `metric_name` | VARCHAR | |
| `value` | FLOAT | |
| `labels` | JSONB | Prometheus-style label set |
| `timestamp` | TIMESTAMPTZ | |

---

## Configuration

All settings read from environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `postgres` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_USER` | `vclaw` | |
| `POSTGRES_PASSWORD` | — | |
| `POSTGRES_DB` | `vclaw_db` | |
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | |
| `KAFKA_TOPIC_WORKFLOW_EVENTS` | `workflow-events` | |
| `KAFKA_TOPIC_SYSTEM_LOGS` | `system-logs` | |
| `KAFKA_CONSUMER_GROUP` | `vclaw-consumer-group` | |
| `LOG_LEVEL` | `INFO` | |
| `METRICS_ENABLED` | `true` | Toggle Prometheus metrics |

---

## Running Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start Postgres and Redis (Docker recommended for local deps)
docker compose up postgres redis -d

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: http://localhost:8000/docs

---

## Kafka Topics

| Topic | Producer | Consumer | Schema |
|-------|----------|----------|--------|
| `workflow-events` | vclaw agent platform | `app/kafka/consumer.py` | `WorkflowEvent` JSON |
| `system-logs` | vclaw agent platform | `app/kafka/consumer.py` | `SystemLog` JSON |

The Kafka consumer runs as a background task in the FastAPI lifespan and inserts records into PostgreSQL. The producer is used by routes that need to emit events programmatically.
