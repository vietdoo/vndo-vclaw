"""Tests for state store and idempotency."""

from __future__ import annotations

import pytest

from vclaw.domain.models import IncomingMessage, TaskStatus, WorkflowState
from vclaw.infrastructure.persistence.state_store import InMemoryStateStore


@pytest.mark.asyncio
async def test_save_and_get() -> None:
    store = InMemoryStateStore()
    msg = IncomingMessage(text="test", chat_id="1", user_id="1")
    ws = WorkflowState(message=msg)

    await store.save(ws)
    retrieved = await store.get(ws.id)
    assert retrieved is not None
    assert retrieved.id == ws.id


@pytest.mark.asyncio
async def test_get_nonexistent() -> None:
    store = InMemoryStateStore()
    assert await store.get("nonexistent") is None


@pytest.mark.asyncio
async def test_idempotency() -> None:
    store = InMemoryStateStore()

    assert await store.check_idempotency("key1") is False
    await store.mark_idempotency("key1")
    assert await store.check_idempotency("key1") is True


@pytest.mark.asyncio
async def test_list_active() -> None:
    store = InMemoryStateStore()

    for status in [TaskStatus.PENDING, TaskStatus.EXECUTING, TaskStatus.COMPLETED]:
        msg = IncomingMessage(text="t", chat_id="1", user_id="1")
        ws = WorkflowState(message=msg, status=status)
        await store.save(ws)

    active = await store.list_active()
    assert len(active) == 2
