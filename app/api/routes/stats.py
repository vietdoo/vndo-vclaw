from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import get_db
from app.schemas.stats import (
    DashboardResponse,
    KafkaStatsResponse,
    LogStatsResponse,
    SystemStatsResponse,
    WorkflowStatsResponse,
)
from app.services.event_service import get_workflow_stats
from app.services.log_service import get_log_stats
from app.services.redis_service import cache_get, cache_set
from app.services.stats_service import get_kafka_stats, get_system_stats

router = APIRouter(prefix="/stats", tags=["stats"])
logger = get_logger(__name__)


@router.get("/system", response_model=SystemStatsResponse)
async def system_stats() -> SystemStatsResponse:
    data = get_system_stats()
    return SystemStatsResponse(**data)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(db: AsyncSession = Depends(get_db)) -> DashboardResponse:
    cached = await cache_get("dashboard_stats")
    if cached:
        return DashboardResponse(**cached)

    system = get_system_stats()
    workflows = await get_workflow_stats(db)
    logs = await get_log_stats(db)
    kafka = await get_kafka_stats(db)

    response_data = {
        "system": system,
        "workflows": workflows,
        "logs": logs,
        "kafka": kafka,
        "generated_at": datetime.utcnow(),
    }

    try:
        await cache_set("dashboard_stats", response_data, ttl=10)
    except Exception as exc:
        logger.warning("cache_set_failed", error=str(exc))

    return DashboardResponse(
        system=SystemStatsResponse(**system),
        workflows=WorkflowStatsResponse(**workflows),
        logs=LogStatsResponse(**logs),
        kafka=KafkaStatsResponse(**kafka),
        generated_at=datetime.utcnow(),
    )
