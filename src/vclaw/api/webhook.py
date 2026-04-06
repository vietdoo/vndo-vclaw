"""Starlette-based API for Telegram webhook and health endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from vclaw.api.dashboard import dashboard_agents, dashboard_events, dashboard_metrics
from vclaw.infrastructure.telegram.gateway import TelegramGateway

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_gateway: TelegramGateway | None = None
_health_data: dict[str, Any] = {}


def set_gateway(gw: TelegramGateway) -> None:
    global _gateway
    _gateway = gw


def set_health_data(data: dict[str, Any]) -> None:
    global _health_data
    _health_data = data


async def telegram_webhook(request: Request) -> Response:
    """Handle incoming Telegram webhook updates."""
    if not _gateway:
        return JSONResponse({"error": "Gateway not initialized"}, status_code=503)

    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    body = await request.body()

    if not _gateway.verify_webhook_signature(body, secret_header):
        logger.warning("webhook_signature_invalid")
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    try:
        update = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    processed = await _gateway.process_update(update)
    return JSONResponse({"ok": True, "processed": processed})


async def health_check(request: Request) -> Response:
    """Health check endpoint for load balancers and monitoring."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "vclaw",
            **_health_data,
        }
    )


async def readiness_check(request: Request) -> Response:
    """Readiness probe for Kubernetes-style deployments."""
    if not _gateway:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return JSONResponse({"status": "ready"})


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    routes = [
        Route("/webhook/telegram", telegram_webhook, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/ready", readiness_check, methods=["GET"]),
        Route("/api/dashboard/metrics", dashboard_metrics, methods=["GET"]),
        Route("/api/dashboard/agents", dashboard_agents, methods=["GET"]),
        Route("/api/dashboard/events", dashboard_events, methods=["GET"]),
    ]

    return Starlette(routes=routes)
