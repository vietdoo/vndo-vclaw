"""REST API endpoints for system monitoring, statistics, and log querying.

Designed to serve a future real-time dashboard frontend.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_platform: Any = None
_start_time: float = time.monotonic()


def set_platform(platform: Any) -> None:
    global _platform, _start_time
    _platform = platform
    _start_time = time.monotonic()


async def system_stats(request: Request) -> Response:
    """Real-time system overview: uptime, components health, throughput."""
    uptime_s = time.monotonic() - _start_time
    data: dict[str, Any] = {
        "status": "healthy",
        "uptime_seconds": round(uptime_s, 1),
        "service": "vclaw",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {},
    }

    if _platform:
        data["components"]["event_bus"] = {
            "backend": _platform.settings.event_bus_backend.value,
            "status": "running" if _platform.event_bus else "not_initialized",
        }
        data["components"]["state_store"] = {
            "backend": _platform.settings.persistence_backend,
            "status": "running" if _platform.state_store else "not_initialized",
        }
        if _platform.agent_registry:
            agents = _platform.agent_registry.agents
            data["components"]["agents"] = {
                "count": len(agents),
                "names": list(agents.keys()),
            }
        if _platform.llm_router:
            health = await _platform.llm_router.health_check_all()
            data["components"]["llm_providers"] = health

    return JSONResponse(data)


async def workflow_stats(request: Request) -> Response:
    """Workflow execution statistics for dashboard charts."""
    since_param = request.query_params.get("since")
    tenant_id = request.query_params.get("tenant_id")

    since = None
    if since_param:
        try:
            since = datetime.fromisoformat(since_param)
        except ValueError:
            hours = int(since_param) if since_param.isdigit() else 24
            since = datetime.now(UTC) - timedelta(hours=hours)

    if _platform and hasattr(_platform, "postgres_store") and _platform.postgres_store:
        stats = await _platform.postgres_store.get_workflow_stats(
            since=since, tenant_id=tenant_id
        )
        return JSONResponse(stats)

    if _platform and _platform.state_store:
        active = await _platform.state_store.list_active()
        return JSONResponse({
            "total_active": len(active),
            "active_workflows": [
                {
                    "id": w.id,
                    "status": w.status.value,
                    "created_at": w.created_at.isoformat(),
                    "tenant_id": w.tenant_id,
                }
                for w in active[:20]
            ],
            "note": "Limited stats — PostgreSQL not configured",
        })

    return JSONResponse({"error": "No state store available"}, status_code=503)


async def event_log(request: Request) -> Response:
    """Query system event log with filters. Supports pagination."""
    if not _platform or not hasattr(_platform, "postgres_store") or not _platform.postgres_store:
        return JSONResponse(
            {"error": "PostgreSQL event log not available"},
            status_code=503,
        )

    event_type = request.query_params.get("event_type")
    correlation_id = request.query_params.get("correlation_id")
    tenant_id = request.query_params.get("tenant_id")
    level = request.query_params.get("level")
    limit = min(int(request.query_params.get("limit", "50")), 500)
    offset = int(request.query_params.get("offset", "0"))

    since = None
    since_param = request.query_params.get("since")
    if since_param:
        try:
            since = datetime.fromisoformat(since_param)
        except ValueError:
            since = None

    until = None
    until_param = request.query_params.get("until")
    if until_param:
        try:
            until = datetime.fromisoformat(until_param)
        except ValueError:
            until = None

    events = await _platform.postgres_store.query_events(
        event_type=event_type,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        level=level,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    total = await _platform.postgres_store.count_events(
        event_type=event_type, since=since, until=until
    )

    return JSONResponse({
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


async def workflow_detail(request: Request) -> Response:
    """Get full detail of a specific workflow by ID."""
    workflow_id = request.path_params["workflow_id"]

    if not _platform or not _platform.state_store:
        return JSONResponse({"error": "State store not available"}, status_code=503)

    state = await _platform.state_store.get(workflow_id)
    if not state:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)

    return JSONResponse(state.model_dump(mode="json"))


async def active_workflows(request: Request) -> Response:
    """List currently active (non-terminal) workflows."""
    if not _platform or not _platform.state_store:
        return JSONResponse({"error": "State store not available"}, status_code=503)

    active = await _platform.state_store.list_active()
    return JSONResponse({
        "count": len(active),
        "workflows": [w.model_dump(mode="json") for w in active[:50]],
    })


async def agent_health(request: Request) -> Response:
    """Health check for all registered agents."""
    if not _platform or not _platform.agent_registry:
        return JSONResponse({"error": "Registry not available"}, status_code=503)

    health = await _platform.agent_registry.health_check_all()
    agents_info = {}
    for name, agent in _platform.agent_registry.agents.items():
        agents_info[name] = {
            "healthy": health.get(name, False),
            "version": agent.manifest.version,
            "description": agent.manifest.description,
            "capabilities": [c.name for c in agent.manifest.capabilities],
            "max_concurrent": agent.manifest.max_concurrent,
            "timeout_seconds": agent.manifest.timeout_seconds,
        }
    return JSONResponse({"agents": agents_info})


async def event_types_summary(request: Request) -> Response:
    """Summary of event types and their counts (last 24h by default)."""
    if not _platform or not hasattr(_platform, "postgres_store") or not _platform.postgres_store:
        return JSONResponse({"error": "PostgreSQL not configured"}, status_code=503)

    hours = int(request.query_params.get("hours", "24"))
    since = datetime.now(UTC) - timedelta(hours=hours)
    pool = _platform.postgres_store._pool

    if not pool:
        return JSONResponse({"error": "DB pool not available"}, status_code=503)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type, COUNT(*) as cnt,
                   MIN(created_at) as first_seen,
                   MAX(created_at) as last_seen
            FROM system_event_log
            WHERE created_at >= $1
            GROUP BY event_type
            ORDER BY cnt DESC
            """,
            since,
        )
        return JSONResponse({
            "period_hours": hours,
            "since": since.isoformat(),
            "event_types": [
                {
                    "event_type": r["event_type"],
                    "count": r["cnt"],
                    "first_seen": r["first_seen"].isoformat(),
                    "last_seen": r["last_seen"].isoformat(),
                }
                for r in rows
            ],
        })


def create_monitoring_routes() -> list[Route]:
    """Create all monitoring/stats API routes."""
    return [
        Route("/api/v1/stats/system", system_stats, methods=["GET"]),
        Route("/api/v1/stats/workflows", workflow_stats, methods=["GET"]),
        Route("/api/v1/stats/events/summary", event_types_summary, methods=["GET"]),
        Route("/api/v1/events", event_log, methods=["GET"]),
        Route("/api/v1/workflows/active", active_workflows, methods=["GET"]),
        Route("/api/v1/workflows/{workflow_id}", workflow_detail, methods=["GET"]),
        Route("/api/v1/agents/health", agent_health, methods=["GET"]),
    ]
