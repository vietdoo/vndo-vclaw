# vndo-vclaw

Vclaw Agent — Workflow automation with real-time monitoring, Kafka event bus, PostgreSQL persistence, and a REST + WebSocket API for frontend tracking.

---

## Architecture

```
                ┌─────────────┐
                │   Frontend  │  (future)
                └──────┬──────┘
                       │ REST / WebSocket
                ┌──────▼──────┐
                │  FastAPI    │  :8000
                │  API + WS   │
                └──┬──┬───┬───┘
          ┌────────┘  │   └────────────┐
    ┌─────▼─────┐  ┌──▼──┐  ┌─────────▼──────┐
    │ PostgreSQL│  │Redis│  │ Kafka (broker) │
    │   :5432   │  │:6379│  │    :9092       │
    └───────────┘  └─────┘  └────────────────┘
                                    │
                          ┌─────────▼────────┐
                          │   Zookeeper      │
                          └──────────────────┘

    ┌──────────────┐    ┌──────────────┐
    │  Prometheus  │    │   Grafana    │
    │    :9090     │◄───│    :3000     │
    └──────────────┘    └──────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API       | FastAPI + uvicorn (uvloop) |
| Messaging | Apache Kafka (Confluent 7.7) |
| Cache / PubSub | Redis 7 |
| Database  | PostgreSQL 16 |
| Migrations | Alembic |
| Metrics   | Prometheus + Grafana |
| Structured logs | structlog (JSON) |
| Containerization | Docker + Docker Compose |
| Load testing | Locust |

---

## Quick Start

```bash
# 1. Clone and enter
git clone <repo>
cd vndo-vclaw

# 2. Copy env config
cp .env.example .env

# 3. Build and start everything
make build
make up

# 4. Verify
curl http://localhost:8000/health
```

Open http://localhost:8000/docs for the interactive API documentation.
Open http://localhost:3000 for Grafana dashboards (admin / admin123).
Open http://localhost:9090 for Prometheus.

---

## API Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Full health check (Postgres, Redis, Kafka) |
| GET | `/live` | Liveness probe |
| GET | `/ready` | Readiness probe |
| GET | `/metrics` | Prometheus metrics |

### Logs (`/api/v1/logs`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/logs` | Create a log entry |
| GET | `/api/v1/logs` | List logs (paginated, filterable) |
| GET | `/api/v1/logs/stats` | Log statistics |

### Workflow Events (`/api/v1/events`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/events` | Create a workflow event |
| GET | `/api/v1/events` | List events (paginated, filterable) |
| GET | `/api/v1/events/{id}` | Get event by ID |
| PATCH | `/api/v1/events/{id}` | Update event status/result |
| GET | `/api/v1/events/stats/summary` | Workflow stats |

### Stats (`/api/v1/stats`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stats/system` | CPU, memory, disk |
| GET | `/api/v1/stats/dashboard` | Full dashboard snapshot (cached 10s) |

### WebSocket (real-time)
| Path | Description |
|------|-------------|
| `ws://localhost:8000/ws/system` | System stats pushed every 2s |
| `ws://localhost:8000/ws/events` | Workflow events via Redis pub/sub |

---

## Development

```bash
# Install deps locally
pip install -r requirements-dev.txt

# Run API locally (need Postgres/Redis/Kafka accessible)
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Load test (stack must be running)
make load-test
```

---

## Fault Tolerance

- **Kafka producer**: `acks=all`, idempotent, retries with exponential backoff (tenacity)
- **Kafka consumer**: auto-reconnect loop, dead-letter logging
- **PostgreSQL**: connection pool with `pool_pre_ping`, `pool_recycle`
- **Redis**: `retry_on_timeout`, non-blocking (cache failures are logged, not raised)
- **API startup**: Kafka/Redis failures are logged as warnings; app starts in degraded mode
- **Docker**: all services have `restart: unless-stopped`, health checks, and resource limits
- **API**: dependency health endpoint (`/health`) reflects live status of all dependencies

---

## Load Testing

```bash
# Start the stack
make up

# Run headless Locust for 60s with 50 concurrent users
make load-test

# Open HTML report
open tests/load_report.html
```
