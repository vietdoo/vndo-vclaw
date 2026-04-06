import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogCreate(BaseModel):
    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    message: str
    source: str | None = None
    logger_name: str | None = None
    trace_id: str | None = None
    extra: dict[str, Any] | None = None


class LogResponse(BaseModel):
    id: uuid.UUID
    level: str
    logger_name: str | None
    message: str
    source: str | None
    trace_id: str | None
    extra: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    total: int
    items: list[LogResponse]
    page: int
    size: int
