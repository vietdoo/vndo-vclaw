from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, str]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
