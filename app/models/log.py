import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    logger_name: Mapped[str] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_system_logs_created_level", "created_at", "level"),
        Index("ix_system_logs_source_created", "source", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SystemLog id={self.id} level={self.level} source={self.source}>"
