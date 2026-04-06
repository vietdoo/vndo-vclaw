"""Workflow state storage with idempotency enforcement."""

from __future__ import annotations

import abc
import asyncio

import structlog

from vclaw.domain.models import WorkflowState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class StateStore(abc.ABC):
    """Abstract state persistence for workflow execution tracking."""

    @abc.abstractmethod
    async def save(self, state: WorkflowState) -> None:
        """Persist or update a workflow state."""

    @abc.abstractmethod
    async def get(self, workflow_id: str) -> WorkflowState | None:
        """Retrieve a workflow state by ID."""

    @abc.abstractmethod
    async def check_idempotency(self, key: str) -> bool:
        """Return True if this idempotency key has been seen before."""

    @abc.abstractmethod
    async def mark_idempotency(self, key: str) -> None:
        """Record an idempotency key as processed."""

    @abc.abstractmethod
    async def list_active(self) -> list[WorkflowState]:
        """List all workflows that are not in terminal states."""


class InMemoryStateStore(StateStore):
    """In-memory state store for development and testing.

    NOT suitable for production -- state is lost on process restart.
    Use Redis or a database-backed implementation for production.
    """

    def __init__(self) -> None:
        self._states: dict[str, WorkflowState] = {}
        self._idempotency_keys: set[str] = set()
        self._lock = asyncio.Lock()

    async def save(self, state: WorkflowState) -> None:
        async with self._lock:
            self._states[state.id] = state

    async def get(self, workflow_id: str) -> WorkflowState | None:
        return self._states.get(workflow_id)

    async def check_idempotency(self, key: str) -> bool:
        return key in self._idempotency_keys

    async def mark_idempotency(self, key: str) -> None:
        async with self._lock:
            self._idempotency_keys.add(key)

    async def list_active(self) -> list[WorkflowState]:
        terminal = {"completed", "failed", "timed_out", "cancelled"}
        return [s for s in self._states.values() if s.status.value not in terminal]
