"""Handler that listens for workflow completion and sends Telegram replies."""

from __future__ import annotations

import structlog

from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.infrastructure.event_bus.base import EventBus
from vclaw.infrastructure.telegram.gateway import TelegramGateway

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ResponseHandler:
    """Subscribes to workflow events and delivers responses via Telegram.

    Bridges the gap between the async orchestrator pipeline and the
    user-facing Telegram chat interface.
    """

    def __init__(
        self,
        event_bus: EventBus,
        telegram_gateway: TelegramGateway,
    ) -> None:
        self._event_bus = event_bus
        self._gateway = telegram_gateway

    async def setup(self) -> None:
        await self._event_bus.subscribe(EventTypes.WORKFLOW_COMPLETED, self._on_completed)
        await self._event_bus.subscribe(EventTypes.WORKFLOW_FAILED, self._on_failed)

    async def _on_completed(self, event: CloudEvent) -> None:
        result = event.data.get("result", {})
        message_data = event.data.get("message", {})
        chat_id = message_data.get("chat_id", "")

        if not chat_id:
            logger.warning("no_chat_id_for_response", event_id=event.id)
            return

        text = result.get("response_text") or result.get("data", {}).get("response_text", "")
        if not text:
            text = "Operation completed successfully." if result.get("data") else "Done."

        await self._gateway.send_message(chat_id, text)
        logger.info("response_delivered", chat_id=chat_id, workflow_id=event.correlation_id)

    async def _on_failed(self, event: CloudEvent) -> None:
        message_data = event.data.get("message", {})
        chat_id = message_data.get("chat_id", "")
        error = event.data.get("error", "Unknown error")

        if not chat_id:
            logger.warning("no_chat_id_for_error", event_id=event.id)
            return

        await self._gateway.send_message(
            chat_id,
            "Sorry, an error occurred while processing your request. Please try again later.",
        )
        logger.info("error_response_delivered", chat_id=chat_id, error=error)
