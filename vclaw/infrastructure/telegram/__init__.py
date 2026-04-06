"""
Telegram integration pipeline:
  - Webhook setup + HMAC signature verification
  - Message normalization → IncomingMessage
  - Idempotency key generation
  - Rate limiting (sliding window per user)
  - Reply delivery
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections import defaultdict, deque
from typing import Any

import httpx
import structlog

from vclaw.domain.exceptions import RateLimitError, TelegramWebhookError
from vclaw.domain.models.base import IncomingMessage, MessageSource, TenantContext

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter per user/chat.
    Stores timestamps of recent requests in a deque per key.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check_and_record(self, key: str) -> None:
        async with self._lock:
            now = time.monotonic()
            window = self._windows[key]
            cutoff = now - self._window
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self._max_requests:
                raise RateLimitError(key)
            window.append(now)


class TelegramClient:
    """Async Telegram Bot API client."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self, bot_token: str, timeout: int = 30) -> None:
        self._token = bot_token
        self._client = httpx.AsyncClient(
            base_url=f"{self.BASE_URL}/bot{bot_token}",
            timeout=timeout,
        )

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "HTML",
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        try:
            resp = await self._client.post("/sendMessage", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "telegram_send_error",
                chat_id=chat_id,
                status=exc.response.status_code,
                body=exc.response.text,
            )
            raise TelegramWebhookError(
                f"send_message failed: {exc.response.status_code}"
            ) from exc

    async def send_typing_action(self, chat_id: str | int) -> None:
        try:
            await self._client.post("/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
        except Exception:
            pass

    async def set_webhook(self, url: str, secret_token: str | None = None) -> bool:
        payload: dict[str, Any] = {"url": url, "allowed_updates": ["message", "callback_query"]}
        if secret_token:
            payload["secret_token"] = secret_token
        resp = await self._client.post("/setWebhook", json=payload)
        return resp.json().get("ok", False)

    async def delete_webhook(self) -> bool:
        resp = await self._client.post("/deleteWebhook")
        return resp.json().get("ok", False)

    async def get_me(self) -> dict[str, Any]:
        resp = await self._client.get("/getMe")
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()


class TelegramMessageNormalizer:
    """
    Converts raw Telegram update payloads into normalized IncomingMessage objects.
    Generates idempotency keys from update_id to ensure at-most-once processing.
    """

    def normalize(self, update: dict[str, Any]) -> IncomingMessage | None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        text = message.get("text") or message.get("caption") or ""
        if not text.strip():
            return None

        chat = message.get("chat", {})
        user = message.get("from", {})
        update_id = update.get("update_id", 0)
        message_id = message.get("message_id", 0)

        idempotency_key = f"tg:{update_id}:{message_id}"

        tenant = TenantContext(
            tenant_id=str(chat.get("id", "unknown")),
            user_id=str(user.get("id", "unknown")),
            chat_id=str(chat.get("id", "unknown")),
            language=user.get("language_code", "vi"),
        )

        attachments: list[dict[str, Any]] = []
        if message.get("photo"):
            attachments.append({"type": "photo", "file_id": message["photo"][-1]["file_id"]})
        if message.get("document"):
            attachments.append({"type": "document", **message["document"]})

        return IncomingMessage(
            idempotency_key=idempotency_key,
            source=MessageSource.TELEGRAM,
            tenant=tenant,
            text=text.strip(),
            attachments=attachments,
            reply_to_message_id=str(message_id),
            raw_payload=update,
        )


class WebhookVerifier:
    """
    Verifies Telegram webhook requests using HMAC-SHA256.
    Uses X-Telegram-Bot-Api-Secret-Token header if configured.
    """

    def __init__(self, bot_token: str, webhook_secret: str | None = None) -> None:
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        # Pre-compute the token key used for update verification
        self._token_key = hashlib.sha256(bot_token.encode()).digest()

    def verify_secret_token(self, header_value: str | None) -> bool:
        """Verify X-Telegram-Bot-Api-Secret-Token header."""
        if not self._webhook_secret:
            return True
        if not header_value:
            return False
        return hmac.compare_digest(header_value, self._webhook_secret)

    def verify_update_signature(
        self, body: bytes, signature_header: str | None
    ) -> bool:
        """
        Verify update body using HMAC-SHA256 with token key.
        Only enforced when webhook_secret is set.
        """
        if not self._webhook_secret:
            return True
        if not signature_header:
            return False
        try:
            expected = hmac.new(self._token_key, body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(f"sha256={expected}", signature_header)
        except Exception:
            return False


class TelegramGateway:
    """
    End-to-end Telegram integration component.
    Wires together: verification → rate limiting → normalization → message dispatch.
    """

    def __init__(
        self,
        bot_token: str,
        rate_limiter: RateLimiter,
        normalizer: TelegramMessageNormalizer,
        verifier: WebhookVerifier,
        on_message_callback: Any,
    ) -> None:
        self._client = TelegramClient(bot_token)
        self._rate_limiter = rate_limiter
        self._normalizer = normalizer
        self._verifier = verifier
        self._on_message = on_message_callback

    async def process_update(
        self,
        update: dict[str, Any],
        secret_token_header: str | None = None,
    ) -> dict[str, str]:
        """
        Process a raw Telegram update through the full pipeline.
        Returns a dict with 'status' key for HTTP response body.
        """
        if not self._verifier.verify_secret_token(secret_token_header):
            logger.warning("webhook_invalid_secret_token")
            return {"status": "unauthorized"}

        message = self._normalizer.normalize(update)
        if message is None:
            return {"status": "ignored"}

        user_id = message.tenant.user_id
        try:
            await self._rate_limiter.check_and_record(user_id)
        except RateLimitError:
            await self._client.send_message(
                message.tenant.chat_id,
                "⚠️ Bạn đang gửi quá nhiều tin nhắn. Vui lòng chờ một chút.",
            )
            return {"status": "rate_limited"}

        await self._client.send_typing_action(message.tenant.chat_id)

        asyncio.create_task(self._handle_and_reply(message))
        return {"status": "accepted"}

    async def _handle_and_reply(self, message: IncomingMessage) -> None:
        try:
            task = await self._on_message(message)
            reply_text = task.final_response or "Đã xử lý xong."
        except Exception as exc:
            logger.exception("handle_and_reply_error", error=str(exc))
            reply_text = "❌ Đã xảy ra lỗi. Vui lòng thử lại."

        try:
            await self._client.send_message(
                chat_id=message.tenant.chat_id,
                text=reply_text,
                reply_to_message_id=int(message.reply_to_message_id)
                if message.reply_to_message_id and message.reply_to_message_id.isdigit()
                else None,
            )
        except Exception as exc:
            logger.error("reply_send_failed", chat_id=message.tenant.chat_id, error=str(exc))

    async def setup_webhook(self, webhook_url: str) -> bool:
        return await self._client.set_webhook(
            webhook_url,
            secret_token=self._verifier._webhook_secret,
        )

    async def start_polling(self) -> None:
        """Long-polling mode for local development without a public URL."""
        await self._client.delete_webhook()
        offset = 0
        logger.info("telegram_polling_started")
        while True:
            try:
                resp = await self._client._client.post(
                    "/getUpdates",
                    json={"offset": offset, "timeout": 30, "limit": 100},
                    timeout=35,
                )
                data = resp.json()
                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue
                for update in data.get("result", []):
                    offset = max(offset, update["update_id"] + 1)
                    asyncio.create_task(
                        self.process_update(update),
                        name=f"update-{update['update_id']}",
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("polling_error", error=str(exc))
                await asyncio.sleep(5)

    async def aclose(self) -> None:
        await self._client.aclose()
