"""Application bootstrap: wires all components and starts the platform."""

from __future__ import annotations

import asyncio
import signal

import structlog
import uvicorn

from vclaw.agents.builtin.public_service import PublicServiceAgent
from vclaw.agents.builtin.task_management import TaskManagementAgent
from vclaw.agents.registry import AgentRegistry
from vclaw.api.monitoring import create_monitoring_routes, set_platform
from vclaw.api.response_handler import ResponseHandler
from vclaw.api.webhook import create_app, set_gateway, set_health_data
from vclaw.application.orchestrator import Orchestrator
from vclaw.config import EventBusBackend, VclawSettings
from vclaw.domain.events import CloudEvent
from vclaw.infrastructure.event_bus.base import EventBus
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus
from vclaw.infrastructure.llm.router import LLMRouter
from vclaw.infrastructure.observability import setup_logging, setup_tracing
from vclaw.infrastructure.persistence.state_store import InMemoryStateStore, StateStore
from vclaw.infrastructure.telegram.gateway import TelegramGateway

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class VclawPlatform:
    """Top-level container that bootstraps and manages all platform components.

    Lifecycle: configure → start → run → stop
    """

    def __init__(self, settings: VclawSettings | None = None) -> None:
        self.settings = settings or VclawSettings()
        self.event_bus: EventBus | None = None
        self.llm_router: LLMRouter | None = None
        self.agent_registry: AgentRegistry | None = None
        self.orchestrator: Orchestrator | None = None
        self.state_store: StateStore | None = None
        self.telegram_gateway: TelegramGateway | None = None
        self.response_handler: ResponseHandler | None = None
        self.postgres_store: object | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize and wire all platform components."""
        setup_logging(
            debug=self.settings.debug,
            json_output=self.settings.environment.value != "development",
        )
        setup_tracing(
            service_name=self.settings.otel_service_name,
            exporter_endpoint=self.settings.otel_exporter_endpoint,
            debug=self.settings.debug,
        )

        logger.info(
            "platform_starting",
            environment=self.settings.environment.value,
            event_bus_backend=self.settings.event_bus_backend.value,
            persistence_backend=self.settings.persistence_backend,
        )

        self.state_store = await self._create_state_store()

        self.event_bus = self._create_event_bus()
        await self.event_bus.start()

        if self.settings.enable_event_logging and self.postgres_store:
            await self._setup_event_logging()

        self.llm_router = LLMRouter.from_configs(self.settings.get_llm_provider_configs())

        self.agent_registry = AgentRegistry(
            event_bus=self.event_bus,
            llm_router=self.llm_router,
        )

        self.orchestrator = Orchestrator(
            event_bus=self.event_bus,
            agent_registry=self.agent_registry,
            llm_router=self.llm_router,
            state_store=self.state_store,
            max_retries=self.settings.orchestrator_max_retries,
        )
        await self.orchestrator.setup()

        self.telegram_gateway = TelegramGateway(
            config=self.settings.telegram,
            event_bus=self.event_bus,
        )

        self.response_handler = ResponseHandler(
            event_bus=self.event_bus,
            telegram_gateway=self.telegram_gateway,
        )
        await self.response_handler.setup()

        await self._register_builtin_agents()

        if self.settings.agent_scan_entrypoints:
            await self.agent_registry.discover_entrypoints()
        if self.settings.agent_plugin_dirs:
            await self.agent_registry.discover_directories(self.settings.agent_plugin_dirs)

        set_gateway(self.telegram_gateway)
        set_health_data(
            {
                "agents": list(self.agent_registry.agents.keys()),
                "event_bus": self.settings.event_bus_backend.value,
                "persistence": self.settings.persistence_backend,
            }
        )
        set_platform(self)

        await self.telegram_gateway.setup_webhook()

        logger.info(
            "platform_started",
            agents=list(self.agent_registry.agents.keys()),
            host=self.settings.host,
            port=self.settings.port,
        )

    async def _register_builtin_agents(self) -> None:
        """Register the built-in agents."""
        assert self.agent_registry is not None
        builtins = [TaskManagementAgent(), PublicServiceAgent()]
        for agent in builtins:
            await self.agent_registry.register(agent)

    def _create_event_bus(self) -> EventBus:
        backend = self.settings.event_bus_backend
        if backend == EventBusBackend.REDIS:
            from vclaw.infrastructure.event_bus.redis_streams import RedisStreamsEventBus

            return RedisStreamsEventBus(redis_url=self.settings.redis.url)
        if backend == EventBusBackend.KAFKA:
            from vclaw.infrastructure.event_bus.kafka_bus import KafkaEventBus

            cfg = self.settings.kafka
            return KafkaEventBus(
                bootstrap_servers=cfg.bootstrap_servers,
                consumer_group=cfg.consumer_group,
                topic_prefix=cfg.topic_prefix,
                max_concurrent=cfg.max_concurrent,
                auto_offset_reset=cfg.auto_offset_reset,
            )
        return InMemoryEventBus(max_concurrent=self.settings.max_concurrent_agents * 10)

    async def _create_state_store(self) -> StateStore:
        if self.settings.persistence_backend == "postgres":
            from vclaw.infrastructure.persistence.postgres_store import PostgresStateStore

            pg = PostgresStateStore(
                dsn=self.settings.postgres.dsn,
                min_pool_size=self.settings.postgres.min_pool_size,
                max_pool_size=self.settings.postgres.max_pool_size,
            )
            try:
                await pg.initialize()
                self.postgres_store = pg
                logger.info("postgres_state_store_ready")
                return pg
            except Exception:
                logger.exception("postgres_init_failed_falling_back_to_memory")
                return InMemoryStateStore()
        return InMemoryStateStore()

    async def _setup_event_logging(self) -> None:
        """Subscribe a bus-wide listener that persists events to PostgreSQL."""
        from vclaw.domain.events import EventTypes

        pg = self.postgres_store
        assert self.event_bus is not None

        event_types_to_log = [
            EventTypes.MESSAGE_RECEIVED,
            EventTypes.MESSAGE_NORMALIZED,
            EventTypes.INTENT_CLASSIFIED,
            EventTypes.TASK_DECOMPOSED,
            EventTypes.AGENT_DISPATCHED,
            EventTypes.AGENT_COMPLETED,
            EventTypes.AGENT_FAILED,
            EventTypes.WORKFLOW_COMPLETED,
            EventTypes.WORKFLOW_FAILED,
            EventTypes.DLQ_MESSAGE,
        ]

        async def _log_event(event: CloudEvent) -> None:
            try:
                level = "error" if "failed" in event.type or "dlq" in event.type else "info"
                await pg.log_event(  # type: ignore[union-attr]
                    event_type=event.type,
                    event_id=event.id,
                    source=event.source,
                    correlation_id=event.correlation_id,
                    tenant_id=event.tenant_id,
                    data=event.data,
                    level=level,
                )
            except Exception:
                logger.debug("event_log_write_failed", event_type=event.type)

        for et in event_types_to_log:
            await self.event_bus.subscribe(et, _log_event)

        logger.info("event_logging_enabled", event_types=len(event_types_to_log))

    async def run(self) -> None:
        """Start the HTTP server and run until shutdown signal."""
        await self.start()

        app = create_app(extra_routes=create_monitoring_routes())
        config = uvicorn.Config(
            app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info" if not self.settings.debug else "debug",
        )
        server = uvicorn.Server(config)

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: self._shutdown_event.set())

        serve_task = asyncio.create_task(server.serve())

        await self._shutdown_event.wait()
        logger.info("shutdown_signal_received")

        server.should_exit = True
        await serve_task
        await self.stop()

    async def stop(self) -> None:
        """Gracefully shut down all components."""
        logger.info("platform_stopping")

        if self.agent_registry:
            await self.agent_registry.shutdown()
        if self.event_bus:
            await self.event_bus.stop()
        if self.llm_router:
            await self.llm_router.close()
        if self.telegram_gateway:
            await self.telegram_gateway.close()
        if self.postgres_store and hasattr(self.postgres_store, "close"):
            await self.postgres_store.close()  # type: ignore[union-attr]

        logger.info("platform_stopped")


def main() -> None:
    """CLI entrypoint."""
    platform = VclawPlatform()
    asyncio.run(platform.run())


if __name__ == "__main__":
    main()
