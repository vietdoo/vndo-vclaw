"""PostgreSQL-backed state store and system event log for production deployments."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog

from vclaw.domain.models import WorkflowState
from vclaw.infrastructure.persistence.state_store import StateStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflow_states (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending',
    message_json    JSONB NOT NULL,
    intent_json     JSONB,
    subtasks_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
    result_json     JSONB,
    error           TEXT,
    tenant_id       TEXT NOT NULL DEFAULT '',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_states(status);
CREATE INDEX IF NOT EXISTS idx_workflow_tenant ON workflow_states(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_created ON workflow_states(created_at);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key         TEXT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_event_log (
    id              BIGSERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'vclaw',
    correlation_id  TEXT NOT NULL DEFAULT '',
    tenant_id       TEXT NOT NULL DEFAULT '',
    data_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    level           TEXT NOT NULL DEFAULT 'info',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON system_event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON system_event_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_log_tenant ON system_event_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_event_log_created ON system_event_log(created_at);
CREATE INDEX IF NOT EXISTS idx_event_log_level ON system_event_log(level);
"""


class PostgresStateStore(StateStore):
    """Production-grade state store backed by PostgreSQL via asyncpg.

    Provides:
    - Durable workflow state persistence
    - Idempotency key tracking with automatic expiry
    - System event log for auditing and analytics
    - Connection pooling for high throughput
    """

    def __init__(
        self,
        dsn: str = "postgresql://vclaw:vclaw@localhost:5432/vclaw",
        min_pool_size: int = 5,
        max_pool_size: int = 20,
    ) -> None:
        self._dsn = dsn
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._pool: Any = None

    async def initialize(self) -> None:
        """Create connection pool and ensure schema exists."""
        import asyncpg

        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_pool_size,
            max_size=self._max_pool_size,
        )
        async with self._pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        logger.info("postgres_state_store_initialized", dsn=self._dsn.split("@")[-1])

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def save(self, state: WorkflowState) -> None:
        if not self._pool:
            raise RuntimeError("PostgresStateStore not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_states
                    (id, status, message_json, intent_json, subtasks_json,
                     result_json, error, tenant_id, retry_count, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    intent_json = EXCLUDED.intent_json,
                    subtasks_json = EXCLUDED.subtasks_json,
                    result_json = EXCLUDED.result_json,
                    error = EXCLUDED.error,
                    retry_count = EXCLUDED.retry_count,
                    updated_at = EXCLUDED.updated_at
                """,
                state.id,
                state.status.value,
                json.dumps(state.message.model_dump(mode="json")),
                json.dumps(state.intent.model_dump()) if state.intent else None,
                json.dumps([s.model_dump(mode="json") for s in state.subtasks]),
                json.dumps(state.result) if state.result else None,
                state.error,
                state.tenant_id,
                state.retry_count,
                state.created_at,
                state.updated_at,
            )

    async def get(self, workflow_id: str) -> WorkflowState | None:
        if not self._pool:
            return None

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE id = $1", workflow_id
            )
            if not row:
                return None
            return self._row_to_state(row)

    async def check_idempotency(self, key: str) -> bool:
        if not self._pool:
            return False

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM idempotency_keys WHERE key = $1", key
            )
            return row is not None

    async def mark_idempotency(self, key: str) -> None:
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO idempotency_keys (key) VALUES ($1) ON CONFLICT DO NOTHING",
                key,
            )

    async def list_active(self) -> list[WorkflowState]:
        if not self._pool:
            return []

        terminal = ("completed", "failed", "timed_out", "cancelled")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflow_states WHERE status NOT IN ($1, $2, $3, $4)"
                " ORDER BY created_at DESC LIMIT 200",
                *terminal,
            )
            return [self._row_to_state(r) for r in rows]

    async def log_event(
        self,
        event_type: str,
        event_id: str,
        source: str = "vclaw",
        correlation_id: str = "",
        tenant_id: str = "",
        data: dict[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        """Write a system event to the persistent audit log."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_event_log
                    (event_type, event_id, source, correlation_id, tenant_id, data_json, level)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                event_type,
                event_id,
                source,
                correlation_id,
                tenant_id,
                json.dumps(data or {}),
                level,
            )

    async def query_events(
        self,
        event_type: str | None = None,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
        level: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query system event log with optional filters."""
        if not self._pool:
            return []

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if event_type:
            conditions.append(f"event_type = ${idx}")
            params.append(event_type)
            idx += 1
        if correlation_id:
            conditions.append(f"correlation_id = ${idx}")
            params.append(correlation_id)
            idx += 1
        if tenant_id:
            conditions.append(f"tenant_id = ${idx}")
            params.append(tenant_id)
            idx += 1
        if level:
            conditions.append(f"level = ${idx}")
            params.append(level)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1
        if until:
            conditions.append(f"created_at <= ${idx}")
            params.append(until)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, offset])

        query = f"""
            SELECT id, event_type, event_id, source, correlation_id,
                   tenant_id, data_json, level, created_at
            FROM system_event_log
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                {
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "event_id": r["event_id"],
                    "source": r["source"],
                    "correlation_id": r["correlation_id"],
                    "tenant_id": r["tenant_id"],
                    "data": json.loads(r["data_json"]) if r["data_json"] else {},
                    "level": r["level"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ]

    async def count_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Count events matching the given filters."""
        if not self._pool:
            return 0

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if event_type:
            conditions.append(f"event_type = ${idx}")
            params.append(event_type)
            idx += 1
        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1
        if until:
            conditions.append(f"created_at <= ${idx}")
            params.append(until)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT COUNT(*) FROM system_event_log {where}"

        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_workflow_stats(
        self,
        since: datetime | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate workflow statistics for dashboard display."""
        if not self._pool:
            return {}

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if since:
            conditions.append(f"created_at >= ${idx}")
            params.append(since)
            idx += 1
        if tenant_id:
            conditions.append(f"tenant_id = ${idx}")
            params.append(tenant_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT status, COUNT(*) as cnt FROM workflow_states {where} GROUP BY status",
                *params,
            )
            status_counts = {r["status"]: r["cnt"] for r in rows}

            total = sum(status_counts.values())
            recent = await conn.fetch(
                f"""
                SELECT id, status, created_at, updated_at, tenant_id
                FROM workflow_states {where}
                ORDER BY updated_at DESC LIMIT 10
                """,
                *params,
            )
            return {
                "total": total,
                "by_status": status_counts,
                "recent": [
                    {
                        "id": r["id"],
                        "status": r["status"],
                        "created_at": r["created_at"].isoformat(),
                        "updated_at": r["updated_at"].isoformat(),
                        "tenant_id": r["tenant_id"],
                    }
                    for r in recent
                ],
            }

    @staticmethod
    def _row_to_state(row: Any) -> WorkflowState:
        from vclaw.domain.models import IncomingMessage, IntentClassification, SubTask

        message_data = json.loads(row["message_json"]) if row["message_json"] else {}
        intent_data = json.loads(row["intent_json"]) if row["intent_json"] else None
        subtasks_data = json.loads(row["subtasks_json"]) if row["subtasks_json"] else []
        result_data = json.loads(row["result_json"]) if row["result_json"] else None

        return WorkflowState(
            id=row["id"],
            status=row["status"],
            message=IncomingMessage.model_validate(message_data),
            intent=IntentClassification.model_validate(intent_data) if intent_data else None,
            subtasks=[SubTask.model_validate(s) for s in subtasks_data],
            result=result_data,
            error=row["error"],
            tenant_id=row["tenant_id"],
            retry_count=row["retry_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
