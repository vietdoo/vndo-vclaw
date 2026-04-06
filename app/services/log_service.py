from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.log import SystemLog
from app.schemas.log import LogCreate, LogListResponse, LogResponse

logger = get_logger(__name__)


async def create_log(db: AsyncSession, data: LogCreate) -> LogResponse:
    log_entry = SystemLog(
        level=data.level,
        message=data.message,
        source=data.source,
        logger_name=data.logger_name,
        trace_id=data.trace_id,
        extra=data.extra or {},
    )
    db.add(log_entry)
    await db.flush()
    return LogResponse.model_validate(log_entry)


async def get_logs(
    db: AsyncSession,
    page: int = 1,
    size: int = 50,
    level: str | None = None,
    source: str | None = None,
    trace_id: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> LogListResponse:
    query = select(SystemLog)

    if level:
        query = query.where(SystemLog.level == level.upper())
    if source:
        query = query.where(SystemLog.source == source)
    if trace_id:
        query = query.where(SystemLog.trace_id == trace_id)
    if from_dt:
        query = query.where(SystemLog.created_at >= from_dt)
    if to_dt:
        query = query.where(SystemLog.created_at <= to_dt)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(desc(SystemLog.created_at)).offset((page - 1) * size).limit(size)
    rows = (await db.execute(query)).scalars().all()

    return LogListResponse(
        total=total,
        items=[LogResponse.model_validate(r) for r in rows],
        page=page,
        size=size,
    )


async def get_log_stats(db: AsyncSession) -> dict:
    level_counts = (
        await db.execute(
            select(SystemLog.level, func.count(SystemLog.id).label("cnt"))
            .group_by(SystemLog.level)
        )
    ).all()

    source_counts = (
        await db.execute(
            select(SystemLog.source, func.count(SystemLog.id).label("cnt"))
            .where(SystemLog.source.isnot(None))
            .group_by(SystemLog.source)
            .order_by(desc("cnt"))
            .limit(10)
        )
    ).all()

    total = sum(row.cnt for row in level_counts)
    level_map = {row.level: row.cnt for row in level_counts}

    return {
        "total_logs": total,
        "debug_count": level_map.get("DEBUG", 0),
        "info_count": level_map.get("INFO", 0),
        "warning_count": level_map.get("WARNING", 0),
        "error_count": level_map.get("ERROR", 0),
        "critical_count": level_map.get("CRITICAL", 0),
        "sources": [{"source": row.source, "count": row.cnt} for row in source_counts],
    }
