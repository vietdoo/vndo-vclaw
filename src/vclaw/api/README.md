# API Layer (`vclaw.api`)

HTTP endpoints (Starlette ASGI) and event-driven response delivery.

## Files

### `webhook.py` — HTTP Endpoints

Starlette routes registered via `create_app()`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook/telegram` | POST | Telegram webhook receiver. Verifies `X-Telegram-Bot-Api-Secret-Token` header via `TelegramGateway.verify_webhook_signature()`, then delegates to `gateway.process_update()`. |
| `/health` | GET | Liveness probe. Returns `{"status": "healthy", "agents": [...], "event_bus": "..."}`. |
| `/ready` | GET | Readiness probe. Returns 503 if gateway is not initialized. |

**Module-level state:** Uses `set_gateway()` and `set_health_data()` to inject dependencies from `app.py` bootstrap.

### `response_handler.py` — Event → Telegram Reply Bridge

`ResponseHandler` subscribes to workflow completion/failure events and sends Telegram replies:

- **`WORKFLOW_COMPLETED`** → Extracts `response_text` from result data → sends to originating `chat_id`
- **`WORKFLOW_FAILED`** → Sends generic error message to originating `chat_id`

**Fallback text:** If no `response_text` is found in the result, defaults to "Operation completed successfully." or "Done."

## Integration Points

- **webhook.py** depends on: `TelegramGateway` (via module-level global)
- **response_handler.py** depends on: `EventBus` (subscribes to `WORKFLOW_COMPLETED`, `WORKFLOW_FAILED`), `TelegramGateway` (sends messages)
