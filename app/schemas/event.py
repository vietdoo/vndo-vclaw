import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowEventCreate(BaseModel):
    workflow_id: str = Field(..., max_length=100)
    workflow_name: str | None = None
    event_type: str = Field(..., max_length=50)
    status: str = Field(..., pattern="^(pending|running|success|failed|retrying|cancelled)$")
    payload: dict[str, Any] | None = None
    trace_id: str | None = None


class WorkflowEventUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(pending|running|success|failed|retrying|cancelled)$")
    result: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: float | None = None


class WorkflowEventResponse(BaseModel):
    id: uuid.UUID
    workflow_id: str
    workflow_name: str | None
    event_type: str
    status: str
    payload: dict[str, Any] | None
    result: dict[str, Any] | None
    error_message: str | None
    duration_ms: float | None
    trace_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowEventListResponse(BaseModel):
    total: int
    items: list[WorkflowEventResponse]
    page: int
    size: int
