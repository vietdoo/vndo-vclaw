from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

registry = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    registry=registry,
)

kafka_messages_produced_total = Counter(
    "kafka_messages_produced_total",
    "Total Kafka messages produced",
    ["topic"],
    registry=registry,
)

kafka_messages_consumed_total = Counter(
    "kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "group"],
    registry=registry,
)

kafka_consumer_lag = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer lag",
    ["topic", "partition"],
    registry=registry,
)

active_websocket_connections = Gauge(
    "active_websocket_connections",
    "Current active WebSocket connections",
    registry=registry,
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    registry=registry,
)

workflow_events_total = Counter(
    "workflow_events_total",
    "Total workflow events processed",
    ["event_type", "status"],
    registry=registry,
)
