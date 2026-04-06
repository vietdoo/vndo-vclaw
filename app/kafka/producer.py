import json
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import kafka_messages_produced_total

logger = get_logger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        raise RuntimeError("Kafka producer not initialized")
    return _producer


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=5,
        retry_backoff_ms=300,
        max_batch_size=16384,
        linger_ms=5,
        compression_type="gzip",
        enable_idempotence=True,
    )
    await _producer.start()
    logger.info("kafka_producer_started", servers=settings.KAFKA_BOOTSTRAP_SERVERS)


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("kafka_producer_stopped")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((KafkaConnectionError, KafkaTimeoutError)),
    reraise=True,
)
async def produce_message(topic: str, value: Any, key: str | None = None) -> None:
    producer = await get_producer()
    try:
        await producer.send_and_wait(topic, value=value, key=key)
        kafka_messages_produced_total.labels(topic=topic).inc()
        logger.debug("kafka_message_produced", topic=topic, key=key)
    except Exception as exc:
        logger.error("kafka_produce_failed", topic=topic, error=str(exc))
        raise


async def produce_workflow_event(workflow_id: str, event_type: str, payload: dict[str, Any]) -> None:
    message = {
        "workflow_id": workflow_id,
        "event_type": event_type,
        "payload": payload,
    }
    await produce_message(
        topic=settings.KAFKA_TOPIC_WORKFLOW_EVENTS,
        value=message,
        key=workflow_id,
    )


async def produce_log_event(level: str, message: str, source: str, extra: dict[str, Any] | None = None) -> None:
    log_msg = {
        "level": level,
        "message": message,
        "source": source,
        "extra": extra or {},
    }
    await produce_message(
        topic=settings.KAFKA_TOPIC_SYSTEM_LOGS,
        value=log_msg,
        key=source,
    )
