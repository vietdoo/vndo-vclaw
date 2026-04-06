"""Unit tests for domain models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from vclaw.domain.models.base import (
    AgentCapability,
    AgentResult,
    IncomingMessage,
    IntentClassification,
    MessageSource,
    OrchestratorTask,
    Priority,
    SubTask,
    TaskStatus,
    TenantContext,
)


def make_tenant() -> TenantContext:
    return TenantContext(tenant_id="t1", user_id="u1", chat_id="c1")


def make_message(text: str = "Hello") -> IncomingMessage:
    return IncomingMessage(
        idempotency_key="key-1",
        source=MessageSource.TELEGRAM,
        tenant=make_tenant(),
        text=text,
    )


class TestTenantContext:
    def test_frozen(self):
        tenant = make_tenant()
        with pytest.raises(Exception):
            tenant.tenant_id = "other"  # type: ignore

    def test_defaults(self):
        tenant = make_tenant()
        assert tenant.language == "vi"
        assert tenant.timezone == "Asia/Ho_Chi_Minh"


class TestIncomingMessage:
    def test_auto_idempotency_key(self):
        msg = IncomingMessage(
            source=MessageSource.API,
            tenant=make_tenant(),
            text="test",
        )
        assert msg.idempotency_key  # auto-generated

    def test_explicit_idempotency_key(self):
        msg = make_message()
        assert msg.idempotency_key == "key-1"

    def test_empty_attachments_by_default(self):
        msg = make_message()
        assert msg.attachments == []


class TestOrchestratorTask:
    def test_initial_status_pending(self):
        task = OrchestratorTask(
            idempotency_key="k1",
            tenant=make_tenant(),
            original_message=make_message(),
        )
        assert task.status == TaskStatus.PENDING

    def test_transition_to(self):
        task = OrchestratorTask(
            idempotency_key="k1",
            tenant=make_tenant(),
            original_message=make_message(),
        )
        task.transition_to(TaskStatus.ROUTING)
        assert task.status == TaskStatus.ROUTING
        assert task.completed_at is None

    def test_transition_to_completed_sets_completed_at(self):
        task = OrchestratorTask(
            idempotency_key="k1",
            tenant=make_tenant(),
            original_message=make_message(),
        )
        task.transition_to(TaskStatus.COMPLETED)
        assert task.completed_at is not None


class TestSubTask:
    def test_auto_id(self):
        st = SubTask(
            parent_task_id="p1",
            capability=AgentCapability.GENERAL,
        )
        assert st.subtask_id

    def test_defaults(self):
        st = SubTask(parent_task_id="p1", capability=AgentCapability.TASK_MANAGEMENT)
        assert st.priority == Priority.NORMAL
        assert st.retry_count == 0
        assert st.max_retries == 3
        assert st.depends_on == []


class TestAgentResult:
    def test_success_result(self):
        result = AgentResult(
            subtask_id="s1",
            agent_id="agent-1",
            success=True,
            output={"message": "done"},
        )
        assert result.success
        assert result.output["message"] == "done"
        assert result.error_message is None

    def test_failure_result(self):
        result = AgentResult(
            subtask_id="s1",
            agent_id="agent-1",
            success=False,
            error_message="Something went wrong",
            error_code="TEST_ERROR",
        )
        assert not result.success
        assert result.error_code == "TEST_ERROR"


class TestIntentClassification:
    def test_valid_confidence(self):
        intent = IntentClassification(
            primary_capability=AgentCapability.TASK_MANAGEMENT,
            confidence=0.95,
        )
        assert intent.confidence == 0.95

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            IntentClassification(
                primary_capability=AgentCapability.GENERAL,
                confidence=1.5,
            )
