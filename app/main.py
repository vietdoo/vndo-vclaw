from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.middleware import RequestLoggingMiddleware
from app.api.routes import events, health, logs, metrics, stats, ws
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.base import engine
from app.kafka.consumer import consumer_manager
from app.kafka.producer import start_producer, stop_producer
from app.services.redis_service import start_redis, stop_redis

setup_logging()
logger = get_logger(__name__)


async def _kafka_workflow_event_handler(message: dict) -> None:
    logger.info(
        "kafka_workflow_event_received",
        workflow_id=message.get("workflow_id"),
        event_type=message.get("event_type"),
    )


async def _kafka_log_handler(message: dict) -> None:
    logger.debug("kafka_log_received", level=message.get("level"), source=message.get("source"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_starting", name=settings.APP_NAME, env=settings.APP_ENV)

    await start_redis()

    try:
        await start_producer()
    except Exception as exc:
        logger.warning("kafka_producer_start_failed", error=str(exc))

    try:
        await consumer_manager.start(
            handlers={
                settings.KAFKA_TOPIC_WORKFLOW_EVENTS: _kafka_workflow_event_handler,
                settings.KAFKA_TOPIC_SYSTEM_LOGS: _kafka_log_handler,
            }
        )
    except Exception as exc:
        logger.warning("kafka_consumer_start_failed", error=str(exc))

    logger.info("app_started")
    yield

    logger.info("app_shutting_down")
    await consumer_manager.stop()
    await stop_producer()
    await stop_redis()
    await engine.dispose()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Vclaw Agent - Workflow automation with real-time monitoring",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    prefix = settings.API_V1_PREFIX
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(ws.router)
    app.include_router(logs.router, prefix=prefix)
    app.include_router(events.router, prefix=prefix)
    app.include_router(stats.router, prefix=prefix)

    return app


app = create_app()
