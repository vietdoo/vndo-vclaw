import asyncio
import json
import time
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import kafka_messages_consumed_total

logger = get_logger(__name__)


class KafkaConsumerManager:
    def __init__(self) -> None:
        self._consumers: dict[str, AIOKafkaConsumer] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self, handlers: dict[str, Callable[[dict], Awaitable[None]]]) -> None:
        self._running = True
        topics = list(handlers.keys())
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            session_timeout_ms=30000,
            heartbeat_interval_ms=3000,
            max_poll_records=100,
        )
        self._consumers["main"] = consumer
        await consumer.start()
        logger.info("kafka_consumer_started", topics=topics, group=settings.KAFKA_CONSUMER_GROUP)

        task = asyncio.create_task(self._consume_loop(consumer, handlers))
        self._tasks.append(task)

    async def _consume_loop(
        self,
        consumer: AIOKafkaConsumer,
        handlers: dict[str, Callable[[dict], Awaitable[None]]],
    ) -> None:
        while self._running:
            try:
                async for msg in consumer:
                    if not self._running:
                        break
                    start = time.monotonic()
                    topic = msg.topic
                    handler = handlers.get(topic)
                    if handler:
                        try:
                            await handler(msg.value)
                            kafka_messages_consumed_total.labels(
                                topic=topic,
                                group=settings.KAFKA_CONSUMER_GROUP,
                            ).inc()
                            elapsed_ms = (time.monotonic() - start) * 1000
                            logger.debug(
                                "kafka_message_consumed",
                                topic=topic,
                                partition=msg.partition,
                                offset=msg.offset,
                                elapsed_ms=round(elapsed_ms, 2),
                            )
                        except Exception as exc:
                            logger.error(
                                "kafka_handler_failed",
                                topic=topic,
                                partition=msg.partition,
                                offset=msg.offset,
                                error=str(exc),
                            )
            except KafkaConnectionError as exc:
                logger.warning("kafka_connection_lost", error=str(exc))
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("kafka_consume_loop_error", error=str(exc))
                await asyncio.sleep(2)

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for consumer in self._consumers.values():
            await consumer.stop()
        logger.info("kafka_consumer_stopped")


consumer_manager = KafkaConsumerManager()
