"""Test fixtures with mocked external dependencies."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """HTTP client with all external dependencies mocked."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one=MagicMock(return_value=1)))

    async def mock_get_db():
        yield mock_db

    with (
        patch("app.db.base.get_db", mock_get_db),
        patch("app.services.redis_service.get_redis", new_callable=AsyncMock) as mock_redis,
        patch("app.kafka.producer.get_producer", new_callable=AsyncMock),
        patch("app.kafka.producer.start_producer", new_callable=AsyncMock),
        patch("app.kafka.consumer.consumer_manager.start", new_callable=AsyncMock),
        patch("app.kafka.consumer.consumer_manager.stop", new_callable=AsyncMock),
        patch("app.services.redis_service.start_redis", new_callable=AsyncMock),
        patch("app.services.redis_service.stop_redis", new_callable=AsyncMock),
    ):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis.return_value = mock_redis_instance

        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
