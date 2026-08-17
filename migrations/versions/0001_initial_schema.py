"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-04-06 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("logger_name", sa.String(200), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_logs_level", "system_logs", ["level"])
    op.create_index("ix_system_logs_source", "system_logs", ["source"])
    op.create_index("ix_system_logs_trace_id", "system_logs", ["trace_id"])
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])
    op.create_index("ix_system_logs_created_level", "system_logs", ["created_at", "level"])
    op.create_index("ix_system_logs_source_created", "system_logs", ["source", "created_at"])

    op.create_table(
        "workflow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(100), nullable=False),
        sa.Column("workflow_name", sa.String(200), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_events_workflow_id", "workflow_events", ["workflow_id"])
    op.create_index("ix_workflow_events_event_type", "workflow_events", ["event_type"])
    op.create_index("ix_workflow_events_status", "workflow_events", ["status"])
    op.create_index("ix_workflow_events_trace_id", "workflow_events", ["trace_id"])
    op.create_index("ix_workflow_events_created_at", "workflow_events", ["created_at"])
    op.create_index("ix_workflow_events_workflow_status", "workflow_events", ["workflow_id", "status"])
    op.create_index("ix_workflow_events_type_created", "workflow_events", ["event_type", "created_at"])

    op.create_table(
        "system_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("labels", postgresql.JSONB, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_metrics_metric_name", "system_metrics", ["metric_name"])
    op.create_index("ix_system_metrics_recorded_at", "system_metrics", ["recorded_at"])
    op.create_index("ix_system_metrics_name_recorded", "system_metrics", ["metric_name", "recorded_at"])

    op.create_table(
        "kafka_message_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("partition", sa.BigInteger, nullable=False),
        sa.Column("offset", sa.BigInteger, nullable=False),
        sa.Column("key", sa.String(200), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("payload_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("processing_ms", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kafka_message_logs_topic", "kafka_message_logs", ["topic"])
    op.create_index("ix_kafka_message_logs_created_at", "kafka_message_logs", ["created_at"])
    op.create_index("ix_kafka_msg_topic_created", "kafka_message_logs", ["topic", "created_at"])


def downgrade() -> None:
    op.drop_table("kafka_message_logs")
    op.drop_table("system_metrics")
    op.drop_table("workflow_events")
    op.drop_table("system_logs")
