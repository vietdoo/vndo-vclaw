from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import get_db
from app.kafka.producer import produce_log_event
from app.schemas.log import LogCreate, LogListResponse, LogResponse
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"])
logger = get_logger(__name__)


@router.post("", response_model=LogResponse, status_code=201)
async def create_log(
    data: LogCreate,
    db: AsyncSession = Depends(get_db),
) -> LogResponse:
    entry = await log_service.create_log(db, data)
    try:
        await produce_log_event(data.level, data.message, data.source or "api", data.extra)
    except Exception as exc:
        logger.warning("kafka_produce_log_skipped", error=str(exc))
    return entry


@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    level: str | None = Query(None),
    source: str | None = Query(None),
    trace_id: str | None = Query(None),
    from_dt: datetime | None = Query(None),
    to_dt: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> LogListResponse:
    return await log_service.get_logs(db, page, size, level, source, trace_id, from_dt, to_dt)


@router.get("/stats")
async def log_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await log_service.get_log_stats(db)
