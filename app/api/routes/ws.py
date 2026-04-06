import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.metrics import active_websocket_connections
from app.services.redis_service import get_redis
from app.services.stats_service import get_system_stats

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        active_websocket_connections.inc()
        logger.info("ws_client_connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        active_websocket_connections.dec()
        logger.info("ws_client_disconnected", total=len(self._connections))

    async def broadcast(self, data: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/system")
async def ws_system_stats(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            stats = get_system_stats()
            stats["timestamp"] = stats["timestamp"].isoformat()
            await websocket.send_json({"type": "system_stats", "data": stats})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/ws/events")
async def ws_workflow_events(websocket: WebSocket) -> None:
    """Stream real-time workflow events via Redis pub/sub."""
    await manager.connect(websocket)
    try:
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("workflow_events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json({"type": "workflow_event", "data": data})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("ws_events_error", error=str(exc))
    finally:
        try:
            await pubsub.unsubscribe("workflow_events")
        except Exception:
            pass
        manager.disconnect(websocket)
