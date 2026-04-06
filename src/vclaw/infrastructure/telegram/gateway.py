"""Telegram API gateway: webhook ingestion, message normalization, response delivery."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import structlog
from opentelemetry import trace

from vclaw.config import TelegramConfig
from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.domain.models import IncomingMessage, MessageSource
from vclaw.infrastructure.event_bus.base import EventBus
from vclaw.infrastructure.telegram.rate_limiter import RateLimiter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class TelegramGateway:
    """Telegram bot integration handling webhook and message lifecycle.

    Responsibilities:
    - Webhook signature verification
    - Raw payload → IncomingMessage normalization
    - Event emission to the bus
    - Rate limiting per chat/user
    - Outbound message delivery
    """

    def __init__(
        self,
        config: TelegramConfig,
        event_bus: EventBus,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._rate_limiter = rate_limiter or RateLimiter(
            max_requests=config.rate_limit_messages,
            window_seconds=config.rate_limit_window_seconds,
        )
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _api_base(self) -> str:
        token = self._config.bot_token.get_secret_value()
        return f"https://api.telegram.org/bot{token}"

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        return self._http_client

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Telegram webhook secret token.

        Uses HMAC-SHA256 comparison to prevent request forgery.
        """
        secret = self._config.webhook_secret.get_secret_value()
        if not secret:
            return True

        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def normalize_update(self, update: dict[str, Any]) -> IncomingMessage | None:
        """Transform a raw Telegram Update into a normalized IncomingMessage."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            callback = update.get("callback_query")
            if callback:
                msg = callback.get("message", {})
                return IncomingMessage(
                    id=str(update.get("update_id", "")),
                    source=MessageSource.TELEGRAM,
                    chat_id=str(msg.get("chat", {}).get("id", "")),
                    user_id=str(callback.get("from", {}).get("id", "")),
                    text=callback.get("data", ""),
                    raw_payload=update,
                )
            return None

        text = message.get("text", "")
        if not text:
            caption = message.get("caption", "")
            text = caption if caption else "[non-text message]"

        return IncomingMessage(
            id=str(update.get("update_id", "")),
            source=MessageSource.TELEGRAM,
            chat_id=str(message.get("chat", {}).get("id", "")),
            user_id=str(message.get("from", {}).get("id", "")),
            text=text,
            raw_payload=update,
        )

    async def process_update(self, update: dict[str, Any]) -> bool:
        """Full pipeline: normalize → rate-check → emit event."""
        with tracer.start_as_current_span("telegram.process_update"):
            message = self.normalize_update(update)
            if not message:
                logger.debug("update_skipped_no_message", update_id=update.get("update_id"))
                return False

            if not self._rate_limiter.allow(message.chat_id):
                logger.warning("rate_limited", chat_id=message.chat_id)
                await self.send_message(
                    message.chat_id,
                    "⏳ Rate limit exceeded. Please wait a moment.",
                )
                return False

            await self._event_bus.publish(
                CloudEvent(
                    type=EventTypes.MESSAGE_RECEIVED,
                    source="vclaw.telegram",
                    data=message.model_dump(mode="json"),
                    subject=message.chat_id,
                )
            )

            await self._event_bus.publish(
                CloudEvent(
                    type=EventTypes.MESSAGE_NORMALIZED,
                    source="vclaw.telegram",
                    data=message.model_dump(mode="json"),
                    subject=message.chat_id,
                )
            )

            logger.info(
                "message_ingested",
                chat_id=message.chat_id,
                user_id=message.user_id,
                text_len=len(message.text),
            )
            return True

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send a message to a Telegram chat."""
        client = self._get_client()
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            resp = await client.post(f"{self._api_base}/sendMessage", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "telegram_send_error",
                status=exc.response.status_code,
                chat_id=chat_id,
            )
            if parse_mode == "Markdown":
                return await self.send_message(
                    chat_id, text, parse_mode="", reply_markup=reply_markup
                )
            return None
        except Exception:
            logger.exception("telegram_send_error", chat_id=chat_id)
            return None

    async def setup_webhook(self) -> bool:
        """Register the webhook URL with Telegram API."""
        if not self._config.webhook_url:
            logger.info("webhook_url_not_configured_skipping")
            return False

        client = self._get_client()
        payload: dict[str, Any] = {
            "url": self._config.webhook_url,
            "allowed_updates": ["message", "edited_message", "callback_query"],
        }

        secret = self._config.webhook_secret.get_secret_value()
        if secret:
            payload["secret_token"] = secret

        try:
            resp = await client.post(f"{self._api_base}/setWebhook", json=payload)
            resp.raise_for_status()
            result = resp.json()
            ok = result.get("ok", False)
            logger.info("webhook_setup", ok=ok, url=self._config.webhook_url)
            return ok
        except Exception:
            logger.exception("webhook_setup_failed")
            return False

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
