"""
FastAPI API Gateway: Telegram webhook endpoint, health checks, and admin APIs.
Handles request validation, rate limiting middleware, and startup/shutdown lifecycle.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vclaw.application.orchestrator import Orchestrator
from vclaw.application.registry import AgentRegistry
from vclaw.config import Settings, get_settings
from vclaw.infrastructure.eventbus import InMemoryEventBus, RedisStreamEventBus
from vclaw.infrastructure.llm import LLMRouter
from vclaw.infrastructure.observability import setup_logging, setup_tracing
from vclaw.infrastructure.telegram import (
    RateLimiter,
    TelegramGateway,
    TelegramMessageNormalizer,
    WebhookVerifier,
)

logger = structlog.get_logger(__name__)

# Application-level singletons (initialized in lifespan)
_registry: AgentRegistry | None = None
_orchestrator: Orchestrator | None = None
_gateway: TelegramGateway | None = None
_event_bus: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    global _registry, _orchestrator, _gateway, _event_bus

    settings = get_settings()
    setup_logging(settings.observability.log_level, settings.observability.log_format)
    setup_tracing(settings.observability.otel_service_name, settings.observability.otel_endpoint)

    logger.info("vclaw_platform_starting", environment=settings.environment)

    # Event bus
    if settings.environment == "development":
        _event_bus = InMemoryEventBus()
    else:
        _event_bus = RedisStreamEventBus(
            redis_url=settings.redis.url,
            stream_prefix=settings.redis.stream_prefix,
            consumer_group=settings.redis.consumer_group,
        )
    await _event_bus.start()

    # LLM router
    llm_router = LLMRouter.from_config(settings.llm)

    # Agent registry + plugin discovery
    _registry = AgentRegistry(
        health_check_interval=settings.agents.health_check_interval_seconds
    )
    await _registry.start()
    await _registry.discover_and_load(settings.agents.plugin_dirs)

    # Orchestrator
    _orchestrator = Orchestrator(
        registry=_registry,
        event_bus=_event_bus,
        llm_router=llm_router,
        max_concurrent_tasks=settings.orchestrator.max_concurrent_tasks,
        task_timeout=settings.orchestrator.task_timeout_seconds,
        idempotency_ttl=settings.orchestrator.idempotency_ttl_seconds,
    )

    # Telegram gateway
    _polling_task: asyncio.Task[None] | None = None
    try:
        tg_token = settings.telegram.bot_token.get_secret_value()
        tg_secret = settings.telegram.webhook_secret.get_secret_value() if settings.telegram.webhook_secret else None
        _gateway = TelegramGateway(
            bot_token=tg_token,
            rate_limiter=RateLimiter(max_requests=10, window_seconds=60),
            normalizer=TelegramMessageNormalizer(),
            verifier=WebhookVerifier(bot_token=tg_token, webhook_secret=tg_secret),
            on_message_callback=_orchestrator.handle_message,
        )
        if settings.telegram.webhook_url:
            ok = await _gateway.setup_webhook(settings.telegram.webhook_url)
            logger.info("telegram_webhook_setup", success=ok, url=settings.telegram.webhook_url)
        # In development mode without webhook, skip polling to avoid blocking tests
        elif settings.environment == "production":
            _polling_task = asyncio.create_task(
                _gateway.start_polling(), name="telegram-polling"
            )
    except Exception as exc:
        logger.warning("telegram_gateway_init_failed", error=str(exc))

    agents = _registry.list_agents()
    logger.info("vclaw_platform_ready", agents=len(agents), agent_ids=[a["agent_id"] for a in agents])

    yield  # Application runs here

    logger.info("vclaw_platform_stopping")
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        await asyncio.gather(_polling_task, return_exceptions=True)
    if _gateway:
        await _gateway.aclose()
    if _registry:
        await _registry.stop()
    if _event_bus:
        await _event_bus.stop()
    logger.info("vclaw_platform_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    cfg = settings or get_settings()

    app = FastAPI(
        title="Vclaw Agent Orchestration Platform",
        description="AI agent orchestration platform with Telegram integration",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if cfg.debug else None,
        redoc_url="/redoc" if cfg.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if cfg.debug else [],
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    # ── Webhook ──────────────────────────────────────────────────────────────

    @app.post("/webhook/telegram", status_code=200)
    async def telegram_webhook(request: Request) -> Response:
        """Receive and process Telegram bot updates."""
        if not _gateway:
            raise HTTPException(status_code=503, detail="Telegram gateway not initialized")

        body = await request.body()
        secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

        try:
            update = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        result = await _gateway.process_update(update, secret_token_header=secret_token)

        if result.get("status") == "unauthorized":
            raise HTTPException(status_code=401, detail="Unauthorized")
        if result.get("status") == "rate_limited":
            return JSONResponse({"status": "rate_limited"}, status_code=429)

        return JSONResponse({"ok": True})

    # ── Health & Readiness ────────────────────────────────────────────────────

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        bus_ok = await _event_bus.health_check() if _event_bus else False
        return {
            "status": "healthy" if bus_ok else "degraded",
            "event_bus": "ok" if bus_ok else "error",
            "agents": len(_registry.list_agents()) if _registry else 0,
        }

    @app.get("/ready", tags=["ops"])
    async def readiness() -> dict[str, str]:
        if not _registry or not _orchestrator:
            raise HTTPException(status_code=503, detail="Platform not ready")
        return {"status": "ready"}

    # ── Admin / Introspection ─────────────────────────────────────────────────

    @app.get("/admin/agents", tags=["admin"])
    async def list_agents() -> dict[str, Any]:
        if not _registry:
            raise HTTPException(status_code=503, detail="Registry not available")
        return {"agents": _registry.list_agents()}

    @app.get("/admin/capabilities", tags=["admin"])
    async def list_capabilities() -> dict[str, Any]:
        if not _registry:
            raise HTTPException(status_code=503, detail="Registry not available")
        return {"capabilities": _registry.all_capabilities()}

    @app.post("/admin/health-check", tags=["admin"])
    async def force_health_check() -> dict[str, str]:
        if not _registry:
            raise HTTPException(status_code=503, detail="Registry not available")
        await _registry._run_health_checks()
        return {"status": "ok"}

    # ── Direct Message API (for testing without Telegram) ────────────────────

    @app.post("/api/v1/message", tags=["api"])
    async def send_message(request: Request) -> dict[str, Any]:
        """
        Process a message directly (non-Telegram clients, testing).
        Body: {"text": "...", "user_id": "...", "chat_id": "..."}
        """
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not ready")

        body = await request.json()
        text = body.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="'text' field required")

        from vclaw.domain.models.base import IncomingMessage, MessageSource, TenantContext

        message = IncomingMessage(
            idempotency_key=body.get("idempotency_key", ""),
            source=MessageSource.API,
            tenant=TenantContext(
                tenant_id=body.get("chat_id", "api-user"),
                user_id=body.get("user_id", "api-user"),
                chat_id=body.get("chat_id", "api-user"),
            ),
            text=text,
            raw_payload=body,
        )

        task = await _orchestrator.handle_message(message)
        return {
            "task_id": task.task_id,
            "status": task.status,
            "response": task.final_response,
            "trace_id": task.trace_id,
        }

    return app


# Module-level app instance for ASGI servers
app = create_app()
