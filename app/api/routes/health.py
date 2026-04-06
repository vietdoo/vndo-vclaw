from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.schemas.common import HealthResponse
from app.services.redis_service import get_redis

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    services: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception as exc:
        logger.error("health_postgres_failed", error=str(exc))
        services["postgres"] = "error"

    try:
        r = await get_redis()
        await r.ping()
        services["redis"] = "ok"
    except Exception as exc:
        logger.warning("health_redis_failed", error=str(exc))
        services["redis"] = "error"

    from app.kafka.producer import get_producer
    try:
        await get_producer()
        services["kafka"] = "ok"
    except Exception:
        services["kafka"] = "error"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        services=services,
    )


@router.get("/ready", tags=["health"])
async def readiness() -> dict:
    return {"status": "ready"}


@router.get("/live", tags=["health"])
async def liveness() -> dict:
    return {"status": "alive"}
