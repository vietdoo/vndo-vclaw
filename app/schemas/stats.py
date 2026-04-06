from datetime import datetime

from pydantic import BaseModel


class SystemStatsResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    timestamp: datetime


class WorkflowStatsResponse(BaseModel):
    total_events: int
    success_count: int
    failed_count: int
    running_count: int
    pending_count: int
    avg_duration_ms: float | None
    success_rate: float


class LogStatsResponse(BaseModel):
    total_logs: int
    debug_count: int
    info_count: int
    warning_count: int
    error_count: int
    critical_count: int
    sources: list[dict]


class KafkaStatsResponse(BaseModel):
    total_produced: int
    total_consumed: int
    total_errors: int
    topics: list[dict]


class DashboardResponse(BaseModel):
    system: SystemStatsResponse
    workflows: WorkflowStatsResponse
    logs: LogStatsResponse
    kafka: KafkaStatsResponse
    generated_at: datetime
