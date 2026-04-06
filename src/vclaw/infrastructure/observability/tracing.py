"""OpenTelemetry tracing setup for distributed trace propagation."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

_tracer_provider: TracerProvider | None = None


def setup_tracing(
    service_name: str = "vclaw",
    exporter_endpoint: str = "",
    debug: bool = False,
) -> TracerProvider:
    """Initialize OpenTelemetry tracing.

    In production, configure an OTLP exporter endpoint.
    In debug mode, spans are exported to the console.
    """
    global _tracer_provider

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if debug:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=exporter_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    return provider


def get_tracer(name: str = "vclaw") -> trace.Tracer:
    """Get a named tracer instance."""
    return trace.get_tracer(name)
