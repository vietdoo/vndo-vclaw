"""Structured logging + OpenTelemetry tracing setup."""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import NonRecordingSpan, Span, SpanContext, TraceFlags


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog with appropriate renderer and log level."""
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level_int)


def setup_tracing(service_name: str, otlp_endpoint: str | None = None) -> TracerProvider:
    """Initialize OpenTelemetry tracing with optional OTLP export."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            logging.warning("OTLP exporter not available, falling back to console")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def inject_trace_context(span: Span) -> dict[str, str]:
    """Extract W3C trace context for propagation across event bus messages."""
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        return {
            "traceparent": f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-{ctx.trace_flags:02x}"
        }
    return {}


def extract_trace_context(headers: dict[str, str]) -> SpanContext | None:
    """Reconstruct span context from W3C traceparent header."""
    traceparent = headers.get("traceparent", "")
    if not traceparent:
        return None
    try:
        parts = traceparent.split("-")
        if len(parts) != 4:
            return None
        _, trace_id_hex, span_id_hex, flags_hex = parts
        return SpanContext(
            trace_id=int(trace_id_hex, 16),
            span_id=int(span_id_hex, 16),
            is_remote=True,
            trace_flags=TraceFlags(int(flags_hex, 16)),
        )
    except (ValueError, IndexError):
        return None
