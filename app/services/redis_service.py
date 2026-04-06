import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


async def start_redis() -> None:
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    await _redis.ping()
    logger.info("redis_connected", url=settings.REDIS_URL.split("@")[-1])


async def stop_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("redis_disconnected")


async def publish(channel: str, data: Any) -> None:
    r = await get_redis()
    await r.publish(channel, json.dumps(data, default=str))


async def cache_set(key: str, value: Any, ttl: int = 30) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    raw = await r.get(key)
    if raw:
        return json.loads(raw)
    return None
