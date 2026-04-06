import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.metrics import http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        start = time.monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.monotonic() - start
            status_code = response.status_code if response else 500
            endpoint = request.url.path

            http_requests_total.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            if not endpoint.startswith(("/health", "/live", "/ready", "/metrics")):
                logger.info(
                    "http_request",
                    method=request.method,
                    path=endpoint,
                    status_code=status_code,
                    duration_ms=round(duration * 1000, 2),
                    trace_id=trace_id,
                )
