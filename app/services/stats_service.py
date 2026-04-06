from datetime import datetime

import psutil
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.metric import KafkaMessageLog

logger = get_logger(__name__)


def get_system_stats() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / 1024 / 1024, 2),
        "memory_total_mb": round(mem.total / 1024 / 1024, 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
        "timestamp": datetime.utcnow(),
    }


async def get_kafka_stats(db: AsyncSession) -> dict:
    rows = (
        await db.execute(
            select(
                KafkaMessageLog.topic,
                KafkaMessageLog.direction,
                func.count(KafkaMessageLog.id).label("cnt"),
                func.sum(
                    (KafkaMessageLog.status == "error").cast(text("integer"))
                ).label("errors"),
            )
            .group_by(KafkaMessageLog.topic, KafkaMessageLog.direction)
        )
    ).all()

    topics: dict[str, dict] = {}
    total_produced = 0
    total_consumed = 0
    total_errors = 0

    for row in rows:
        if row.topic not in topics:
            topics[row.topic] = {"topic": row.topic, "produced": 0, "consumed": 0, "errors": 0}
        if row.direction == "out":
            topics[row.topic]["produced"] += row.cnt
            total_produced += row.cnt
        else:
            topics[row.topic]["consumed"] += row.cnt
            total_consumed += row.cnt
        errors = int(row.errors or 0)
        topics[row.topic]["errors"] += errors
        total_errors += errors

    return {
        "total_produced": total_produced,
        "total_consumed": total_consumed,
        "total_errors": total_errors,
        "topics": list(topics.values()),
    }
