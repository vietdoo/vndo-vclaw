"""Unit tests for Telegram integration components."""
from __future__ import annotations

import pytest

from vclaw.domain.models.base import MessageSource
from vclaw.infrastructure.telegram import (
    RateLimiter,
    TelegramMessageNormalizer,
    WebhookVerifier,
)
from vclaw.domain.exceptions import RateLimitError


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            await limiter.check_and_record("user-1")

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            await limiter.check_and_record("user-1")
        with pytest.raises(RateLimitError):
            await limiter.check_and_record("user-1")

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        await limiter.check_and_record("user-1")
        await limiter.check_and_record("user-1")
        # user-2 should be unaffected
        await limiter.check_and_record("user-2")


class TestTelegramMessageNormalizer:
    def test_normalize_text_message(self):
        normalizer = TelegramMessageNormalizer()
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 99,
                "from": {"id": 111, "language_code": "vi"},
                "chat": {"id": 222},
                "text": "Tạo task mới",
            },
        }
        msg = normalizer.normalize(update)
        assert msg is not None
        assert msg.text == "Tạo task mới"
        assert msg.source == MessageSource.TELEGRAM
        assert msg.tenant.user_id == "111"
        assert msg.tenant.chat_id == "222"
        assert msg.idempotency_key == "tg:12345:99"

    def test_normalize_empty_text_returns_none(self):
        normalizer = TelegramMessageNormalizer()
        update = {
            "update_id": 1,
            "message": {"message_id": 1, "from": {"id": 1}, "chat": {"id": 1}, "text": ""},
        }
        assert normalizer.normalize(update) is None

    def test_normalize_no_message_returns_none(self):
        normalizer = TelegramMessageNormalizer()
        update = {"update_id": 1, "channel_post": {}}
        assert normalizer.normalize(update) is None

    def test_language_code_preserved(self):
        normalizer = TelegramMessageNormalizer()
        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 1, "language_code": "en"},
                "chat": {"id": 1},
                "text": "Hello",
            },
        }
        msg = normalizer.normalize(update)
        assert msg.tenant.language == "en"


class TestWebhookVerifier:
    def test_no_secret_always_passes(self):
        verifier = WebhookVerifier("test_token")
        assert verifier.verify_secret_token(None) is True
        assert verifier.verify_secret_token("anything") is True

    def test_correct_secret_passes(self):
        verifier = WebhookVerifier("test_token", webhook_secret="my_secret")
        assert verifier.verify_secret_token("my_secret") is True

    def test_wrong_secret_fails(self):
        verifier = WebhookVerifier("test_token", webhook_secret="my_secret")
        assert verifier.verify_secret_token("wrong_secret") is False

    def test_missing_secret_header_fails(self):
        verifier = WebhookVerifier("test_token", webhook_secret="my_secret")
        assert verifier.verify_secret_token(None) is False
