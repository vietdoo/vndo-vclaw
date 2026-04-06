# Infrastructure Layer (`vclaw.infrastructure`)

External-facing implementations: event bus backends, LLM providers, persistence, Telegram integration, and observability. All modules expose abstract interfaces that concrete implementations fulfill.

## Subsystems

### `event_bus/` — Async Pub/Sub Event Bus

**Abstract interface (`base.py`):**
- `EventBus` with methods: `publish()`, `subscribe()`, `unsubscribe()`, `start()`, `stop()`, `publish_to_dlq()`
- `EventHandler` type: `Callable[[CloudEvent], Coroutine[Any, Any, None]]`
- Guarantees: at-least-once delivery, message ordering within a subject, DLQ routing

**Implementations:**

| Backend | File | Use Case | Key Features |
|---------|------|----------|--------------|
| InMemory | `memory.py` | Development/testing | Semaphore-based backpressure, asyncio task dispatch, in-memory DLQ list |
| Redis Streams | `redis_streams.py` | Production | Consumer groups, automatic ack, configurable batch/block, dedicated DLQ stream |
| NATS | *(planned)* | High-throughput | Declared in config, raises `NotImplementedError` |

### `llm/` — LLM Provider Abstraction

**Abstract interface (`base.py`):**
- `LLMProvider` with methods: `complete()`, `health_check()`, `close()`
- Constructor: `name`, `api_key`, `base_url`, `model`

**`OpenAICompatProvider` (`openai_compat.py`):**
- Works with any OpenAI-compatible API: OpenAI, OpenRouter, Azure OpenAI, vLLM, Ollama
- Uses `httpx.AsyncClient` with connection pooling
- Handles tool-calling via standard function calling protocol
- Calculates cost estimates from token usage and configured rates

**`LLMRouter` (`router.py`):**
- Priority-based provider selection (lower number = higher priority)
- Automatic fallback chain on failure
- Health tracking with async lock — failed providers are marked unhealthy and skipped
- `reset_provider()` to re-enable a provider after recovery
- `health_check_all()` for batch health verification

### `persistence/` — Workflow State Storage

**Abstract interface (`state_store.py`):**
- `StateStore` with methods: `save()`, `get()`, `check_idempotency()`, `mark_idempotency()`, `list_active()`

**`InMemoryStateStore`:**
- Dict-based storage with `asyncio.Lock` for thread safety
- Idempotency via `set[str]` of processed keys
- **Not production-suitable** — state is lost on restart

### `telegram/` — Telegram Bot Integration

**`TelegramGateway` (`gateway.py`):**
- Webhook signature verification (HMAC-SHA256)
- Raw Update → `IncomingMessage` normalization (handles `message`, `edited_message`, `callback_query`)
- Rate limiting per `chat_id` via `RateLimiter`
- Outbound message delivery with Markdown fallback
- Webhook URL registration on startup

**`RateLimiter` (`rate_limiter.py`):**
- Sliding-window algorithm keyed by identifier (chat_id, user_id)
- Configurable `max_requests` and `window_seconds`
- `allow()`, `reset()`, `remaining()` methods

### `observability/` — Logging & Tracing

**`setup_logging()` (`logging.py`):**
- structlog with JSON (production) or colored console (development) rendering
- Context variable propagation for tenant/workflow context
- Noisy loggers (`httpx`, `httpcore`, `asyncio`) suppressed to WARNING

**`setup_tracing()` (`tracing.py`):**
- OpenTelemetry `TracerProvider` with configurable service name
- Console exporter in debug mode, OTLP/gRPC exporter for production
- `get_tracer()` convenience function

## Configuration

All infrastructure is configured via `VclawSettings` (`config.py`):
- `event_bus_backend`: `memory` | `redis` | `nats`
- `redis.*`: Redis connection settings
- `nats.*`: NATS connection settings
- `telegram.*`: Bot token, webhook URL, rate limits
- `llm_providers`: List of provider configs (name, api_key, base_url, model, priority, cost)
- `otel_*`: OpenTelemetry service name and exporter endpoint
