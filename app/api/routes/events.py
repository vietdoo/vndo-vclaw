import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import get_db
from app.kafka.producer import produce_workflow_event
from app.schemas.event import (
    WorkflowEventCreate,
    WorkflowEventListResponse,
    WorkflowEventResponse,
    WorkflowEventUpdate,
)
from app.services import event_service
from app.services.redis_service import publish

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger(__name__)


@router.post("", response_model=WorkflowEventResponse, status_code=201)
async def create_event(
    data: WorkflowEventCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEventResponse:
    event = await event_service.create_event(db, data)
    try:
        await produce_workflow_event(data.workflow_id, data.event_type, data.payload or {})
    except Exception as exc:
        logger.warning("kafka_produce_event_skipped", error=str(exc))
    try:
        await publish("workflow_events", {"id": str(event.id), "type": data.event_type, "status": data.status})
    except Exception as exc:
        logger.warning("redis_publish_skipped", error=str(exc))
    return event


@router.patch("/{event_id}", response_model=WorkflowEventResponse)
async def update_event(
    event_id: uuid.UUID,
    data: WorkflowEventUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEventResponse:
    event = await event_service.update_event(db, event_id, data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{event_id}", response_model=WorkflowEventResponse)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEventResponse:
    event = await event_service.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("", response_model=WorkflowEventListResponse)
async def list_events(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    workflow_id: str | None = Query(None),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    from_dt: datetime | None = Query(None),
    to_dt: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> WorkflowEventListResponse:
    return await event_service.get_events(db, page, size, workflow_id, event_type, status, from_dt, to_dt)


@router.get("/stats/summary")
async def workflow_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await event_service.get_workflow_stats(db)
