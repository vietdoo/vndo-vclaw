# Infrastructure Layer — `vclaw.infrastructure`

This package contains all I/O-bound adapters: event bus backends, LLM providers, state persistence, Telegram gateway, and observability tooling. It implements the interfaces defined in the domain and application layers.

## Sub-packages

| Sub-package | Role |
|-------------|------|
| `event_bus/` | Async pub/sub with in-memory and Redis Streams backends |
| `llm/` | LLM provider abstraction with OpenAI-compatible client and router |
| `persistence/` | Workflow state and idempotency storage |
| `telegram/` | Telegram Bot API gateway and rate limiter |
| `observability/` | Structured logging (structlog) and OpenTelemetry tracing |

---

## `event_bus/`

### `base.py` — `EventBus` (abstract)

```python
class EventBus(abc.ABC):
    async def publish(event: CloudEvent) -> None: ...
    async def subscribe(event_type: str, handler: Callable) -> None: ...
    async def unsubscribe(event_type: str, handler: Callable) -> None: ...
    async def close() -> None: ...
```

All handlers receive a `CloudEvent` and must be `async def`.

### `memory.py` — `InMemoryEventBus`

- **Use case:** Development, unit tests.
- **Delivery:** Direct async dispatch to all subscribed handlers.
- **Backpressure:** Configurable `max_concurrent` semaphore (default: 100).
- **DLQ:** Failed handler exceptions are logged but do not crash the bus.

### `redis_streams.py` — `RedisStreamsEventBus`

- **Use case:** Production; survives restarts and scales horizontally.
- **Stream key:** `vclaw:events:{event_type}` per event type.
- **Consumer groups:** Ensures at-least-once delivery with consumer group ACKs.
- **Dead-letter:** Failed events written to `vclaw:dlq` stream.
- **Configuration:** Requires `REDIS_URL` in environment.

### Switching backends

Set `VCLAW_EVENT_BUS_BACKEND` environment variable:
- `memory` — `InMemoryEventBus` (default)
- `redis` — `RedisStreamsEventBus`

---

## `llm/`

### `base.py` — `LLMProvider` (abstract)

```python
class LLMProvider(abc.ABC):
    name: str
    async def complete(request: LLMRequest) -> LLMResponse: ...
    async def health_check() -> bool: ...
    async def close() -> None: ...
```

### `openai_compat.py` — `OpenAICompatProvider`

Implements `LLMProvider` against any OpenAI-compatible REST API:

| Parameter | Description |
|-----------|-------------|
| `api_key` | Bearer token |
| `base_url` | Endpoint — OpenAI, OpenRouter, Ollama, vLLM, etc. |
| `model` | Model name (overridable per-request) |
| `timeout_seconds` | Per-request HTTP timeout |
| `cost_per_1k_input` / `cost_per_1k_output` | For cost tracking in `LLMResponse.cost_estimate` |

Uses `httpx.AsyncClient` with connection pooling.

### `router.py` — `LLMRouter`

Priority-based fallback chain across multiple providers:

```python
router = LLMRouter.from_configs([
    LLMProviderConfig(name="openai", priority=1, api_key="sk-...", model="gpt-4o-mini"),
    LLMProviderConfig(name="openrouter", priority=2, api_key="...", base_url="https://openrouter.ai/api/v1", model="..."),
])
```

**Routing logic:**
1. Try providers in ascending `priority` order.
2. On failure → mark provider unhealthy, try next.
3. All fail → raise `RuntimeError`.
4. `reset_provider(name)` clears unhealthy flag for retry.

**Health checks:** `health_check_all()` pings all providers and updates health state.

---

## `persistence/`

### `state_store.py` — `StateStore`

```python
class StateStore:
    async def save(workflow: WorkflowState) -> None: ...
    async def get(workflow_id: str) -> WorkflowState | None: ...
    async def check_idempotency(key: str) -> bool: ...
    async def mark_idempotency(key: str) -> None: ...
```

**Current implementation:** In-memory dict. Thread-safe for single-process use.

**Production upgrade path:** Replace with a Redis or PostgreSQL backend by subclassing or reimplementing the same interface. The orchestrator never imports the concrete class directly — it receives the instance via dependency injection.

---

## `telegram/`

### `gateway.py` — `TelegramGateway`

Wraps the Telegram Bot API:

| Method | Description |
|--------|-------------|
| `send_message(chat_id, text)` | Send text reply (MarkdownV2 formatted) |
| `set_webhook(url, secret_token)` | Register webhook URL on startup |
| `delete_webhook()` | Remove webhook (used in shutdown) |

Uses `httpx.AsyncClient` with retry on transient failures (tenacity).

### `rate_limiter.py` — Per-chat sliding window

- Default: 20 messages / 60 seconds per `chat_id`.
- Configurable via `TELEGRAM_RATE_LIMIT_MESSAGES` and `TELEGRAM_RATE_LIMIT_WINDOW_SECONDS`.
- Returns `bool` from `allow(chat_id)` — caller decides whether to reject or queue.

---

## `observability/`

### `logging.py`

Configures **structlog** with:
- `structlog.contextvars` for async-safe context propagation.
- JSON output in production (`VCLAW_ENVIRONMENT=production`), colored dev output otherwise.
- Standard fields: `timestamp`, `level`, `event`, `logger`.

**Usage in modules:**
```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("event_name", key="value", workflow_id="...")
```

**Binding context** (e.g., per-request middleware):
```python
structlog.contextvars.bind_contextvars(tenant_id="t-001", workflow_id="wf-...")
```

### `tracing.py`

Helpers for **OpenTelemetry** span creation:
- `get_tracer(name)` — returns a named tracer (wraps `opentelemetry.trace.get_tracer`).
- Span attributes follow the `agent.*` / `workflow.*` / `llm.*` naming convention.

Configure the exporter via standard OTel env vars:
- `OTEL_EXPORTER_OTLP_ENDPOINT` — for Jaeger, Tempo, etc.
- `OTEL_SERVICE_NAME` — defaults to `vclaw`.

---

## Adding a New Infrastructure Adapter

1. Create a sub-package under `infrastructure/`.
2. Define an abstract base class (interface) if multiple implementations are expected.
3. Inject the concrete implementation via `VclawPlatform` in `src/vclaw/app.py`.
4. Add config keys to `src/vclaw/config.py` with `pydantic-settings` fields.
5. Add a test in `tests/` using async fixtures (see `conftest.py`).
