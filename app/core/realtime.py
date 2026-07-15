import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket


class RealtimeConnectionManager:
    """In-process, project-scoped WebSocket fan-out."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, project_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[project_id].add(websocket)

    async def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(project_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(project_id, None)

    async def publish(self, project_id: int, event: dict[str, Any]) -> None:
        payload = {**event, "project_id": project_id, "created_at": datetime.now(UTC).isoformat()}
        async with self._lock:
            connections = tuple(self._connections.get(project_id, ()))
        stale: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(project_id, websocket)


manager = RealtimeConnectionManager()


def infer_realtime_events(method: str, path: str) -> set[str]:
    if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return set()
    if path in {"/api/login", "/api/users", "/api/email/verify", "/api/email/resend", "/api/password/forgot", "/api/password/reset"}:
        return set()
    events = {"logs.changed"}
    if "/chat/" in path or "/dice/" in path:
        events.add("chat.changed")
    if "/game-recruitments" in path:
        events.add("recruitment.changed")
    if "/characters" in path or "/karma-shop" in path:
        events.add("character.changed")
    if any(part in path for part in ("/inventory", "/shop/", "/market", "/karma-shop")):
        events.add("market.changed")
    if "/users" in path or "/projects" in path:
        events.add("user.changed")
    return events


async def publish_realtime_event(
    project_id: int,
    event_type: str,
    *,
    entity_id: int | None = None,
    user_id: int | None = None,
) -> None:
    event: dict[str, Any] = {"type": event_type}
    if entity_id is not None:
        event["entity_id"] = entity_id
    if user_id is not None:
        event["user_id"] = user_id
    await manager.publish(project_id, event)
