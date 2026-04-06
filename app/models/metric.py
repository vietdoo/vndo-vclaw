import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=True)
    labels: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_system_metrics_name_recorded", "metric_name", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<SystemMetric name={self.metric_name} value={self.metric_value}>"


class KafkaMessageLog(Base):
    __tablename__ = "kafka_message_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    partition: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset: Mapped[int] = mapped_column(BigInteger, nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "in" or "out"
    payload_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    processing_ms: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_kafka_msg_topic_created", "topic", "created_at"),
    )
