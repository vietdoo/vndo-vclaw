import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import workflow_events_total
from app.models.event import WorkflowEvent
from app.schemas.event import WorkflowEventCreate, WorkflowEventListResponse, WorkflowEventResponse, WorkflowEventUpdate

logger = get_logger(__name__)


async def create_event(db: AsyncSession, data: WorkflowEventCreate) -> WorkflowEventResponse:
    event = WorkflowEvent(
        workflow_id=data.workflow_id,
        workflow_name=data.workflow_name,
        event_type=data.event_type,
        status=data.status,
        payload=data.payload or {},
        trace_id=data.trace_id,
    )
    db.add(event)
    await db.flush()
    workflow_events_total.labels(event_type=data.event_type, status=data.status).inc()
    return WorkflowEventResponse.model_validate(event)


async def update_event(
    db: AsyncSession, event_id: uuid.UUID, data: WorkflowEventUpdate
) -> WorkflowEventResponse | None:
    result = await db.execute(select(WorkflowEvent).where(WorkflowEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return None

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(event, field, value)
    event.updated_at = datetime.utcnow()
    await db.flush()

    if data.status:
        workflow_events_total.labels(event_type=event.event_type, status=data.status).inc()

    return WorkflowEventResponse.model_validate(event)


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> WorkflowEventResponse | None:
    result = await db.execute(select(WorkflowEvent).where(WorkflowEvent.id == event_id))
    event = result.scalar_one_or_none()
    return WorkflowEventResponse.model_validate(event) if event else None


async def get_events(
    db: AsyncSession,
    page: int = 1,
    size: int = 50,
    workflow_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> WorkflowEventListResponse:
    query = select(WorkflowEvent)

    if workflow_id:
        query = query.where(WorkflowEvent.workflow_id == workflow_id)
    if event_type:
        query = query.where(WorkflowEvent.event_type == event_type)
    if status:
        query = query.where(WorkflowEvent.status == status)
    if from_dt:
        query = query.where(WorkflowEvent.created_at >= from_dt)
    if to_dt:
        query = query.where(WorkflowEvent.created_at <= to_dt)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(desc(WorkflowEvent.created_at)).offset((page - 1) * size).limit(size)
    rows = (await db.execute(query)).scalars().all()

    return WorkflowEventListResponse(
        total=total,
        items=[WorkflowEventResponse.model_validate(r) for r in rows],
        page=page,
        size=size,
    )


async def get_workflow_stats(db: AsyncSession) -> dict:
    status_counts = (
        await db.execute(
            select(WorkflowEvent.status, func.count(WorkflowEvent.id).label("cnt"))
            .group_by(WorkflowEvent.status)
        )
    ).all()

    avg_duration = (
        await db.execute(
            select(func.avg(WorkflowEvent.duration_ms)).where(WorkflowEvent.duration_ms.isnot(None))
        )
    ).scalar_one_or_none()

    total = sum(row.cnt for row in status_counts)
    status_map = {row.status: row.cnt for row in status_counts}
    success = status_map.get("success", 0)

    return {
        "total_events": total,
        "success_count": success,
        "failed_count": status_map.get("failed", 0),
        "running_count": status_map.get("running", 0),
        "pending_count": status_map.get("pending", 0),
        "avg_duration_ms": round(float(avg_duration), 2) if avg_duration else None,
        "success_rate": round((success / total) * 100, 2) if total > 0 else 0.0,
    }
