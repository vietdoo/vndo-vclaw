"""Dashboard API endpoints for real-time metrics and agent monitoring."""

from __future__ import annotations

import time
from typing import Any

import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_platform_ref: Any = None
_start_time: float = time.monotonic()
_request_count: int = 0
_tool_call_count: int = 0


def set_platform(platform: Any) -> None:
    global _platform_ref
    _platform_ref = platform


def track_request() -> None:
    global _request_count
    _request_count += 1


def track_tool_call() -> None:
    global _tool_call_count
    _tool_call_count += 1


async def dashboard_metrics(request: Request) -> Response:
    """Return platform-wide metrics for the dashboard."""
    uptime = time.monotonic() - _start_time
    agents: list[str] = []
    if _platform_ref and _platform_ref.agent_registry:
        agents = list(_platform_ref.agent_registry.agents.keys())

    return JSONResponse(
        {
            "totalRequests": _request_count,
            "activeWorkflows": 0,
            "avgLatencyMs": 0,
            "successRate": 100.0,
            "agentCount": len(agents),
            "eventsPerSecond": 0,
            "uptimeSeconds": int(uptime),
            "totalToolCalls": _tool_call_count,
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def dashboard_agents(request: Request) -> Response:
    """Return registered agent info for the dashboard."""
    agents: list[dict[str, Any]] = []

    if _platform_ref and _platform_ref.agent_registry:
        for name, agent in _platform_ref.agent_registry.agents.items():
            manifest = agent.manifest
            healthy = True
            try:
                healthy = await agent.health_check()
            except Exception:
                healthy = False

            agents.append(
                {
                    "name": name,
                    "status": "online" if healthy else "degraded",
                    "version": manifest.version,
                    "capabilities": [c.name for c in manifest.capabilities],
                    "tools": [t.name for t in manifest.tools],
                    "maxConcurrent": manifest.max_concurrent,
                    "enabled": manifest.enabled,
                }
            )

    return JSONResponse(
        {"agents": agents},
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def dashboard_events(request: Request) -> Response:
    """Return recent events (placeholder for SSE upgrade)."""
    return JSONResponse(
        {"events": []},
        headers={"Access-Control-Allow-Origin": "*"},
    )
