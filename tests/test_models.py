"""Tests for domain models and validation."""

from __future__ import annotations

from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
    IncomingMessage,
    IntentClassification,
    LLMRequest,
    MessageSource,
    SubTask,
    TaskStatus,
    ToolDefinition,
    WorkflowState,
)


def test_incoming_message_defaults() -> None:
    msg = IncomingMessage(text="hello", chat_id="123", user_id="456")
    assert msg.source == MessageSource.TELEGRAM
    assert msg.id
    assert "123" in msg.idempotency_key
    assert msg.text == "hello"


def test_incoming_message_idempotency_key_format() -> None:
    msg = IncomingMessage(source=MessageSource.TELEGRAM, chat_id="abc", user_id="def", text="test")
    assert msg.idempotency_key.startswith("telegram:abc:")


def test_workflow_state_transition() -> None:
    msg = IncomingMessage(text="test", chat_id="1", user_id="1")
    ws = WorkflowState(message=msg)
    assert ws.status == TaskStatus.PENDING

    ws.transition(TaskStatus.ROUTING)
    assert ws.status == TaskStatus.ROUTING


def test_agent_manifest_serialization() -> None:
    manifest = AgentManifest(
        name="test_agent",
        capabilities=[AgentCapability(name="test", description="A test capability")],
        tools=[
            ToolDefinition(
                name="do_thing",
                description="Does a thing",
                parameters={"x": {"type": "string"}},
                required_params=["x"],
            )
        ],
    )
    data = manifest.model_dump()
    assert data["name"] == "test_agent"
    assert len(data["capabilities"]) == 1
    assert len(data["tools"]) == 1


def test_cloud_event_correlation_id() -> None:
    event = CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={"text": "hi"})
    assert event.correlation_id == event.id
    assert event.specversion == "1.0"


def test_cloud_event_custom_correlation() -> None:
    event = CloudEvent(
        type=EventTypes.AGENT_DISPATCHED,
        correlation_id="custom-123",
        data={},
    )
    assert event.correlation_id == "custom-123"


def test_intent_classification() -> None:
    ic = IntentClassification(
        intent="task_creation",
        confidence=0.95,
        target_agent="task_management",
        parameters={"team": "backend"},
    )
    assert ic.confidence == 0.95
    assert ic.target_agent == "task_management"


def test_subtask_defaults() -> None:
    st = SubTask(agent_name="test")
    assert st.status == TaskStatus.PENDING
    assert st.result is None
    assert st.depends_on == []


def test_agent_request_response() -> None:
    req = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="test",
        input_data={"text": "hello"},
    )
    assert req.timeout_seconds == 60.0

    resp = AgentResponse(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="test",
        success=True,
        data={"result": "done"},
    )
    assert resp.success
    assert resp.data["result"] == "done"


def test_llm_request() -> None:
    req = LLMRequest(
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.5,
    )
    assert req.temperature == 0.5
    assert len(req.messages) == 1
