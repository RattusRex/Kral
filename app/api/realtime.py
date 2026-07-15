from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import func

from app.api.projects import get_project_access
from app.core.realtime import manager
from app.core.security import verify_access_token
from app.db.database import SessionLocal
from app.models.user import User


router = APIRouter(tags=["realtime"])


async def reject(websocket: WebSocket, detail: str, code: int = 4401) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "connection.error", "detail": detail})
    await websocket.close(code=code)


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket, token: str | None = None, project_id: int | None = None):
    # Browsers cannot attach an Authorization header during the WebSocket
    # handshake. The short-lived JWT therefore travels in the TLS-protected
    # query string and is validated before project access is granted.
    if not token:
        await reject(websocket, "Authentication required")
        return
    if project_id is None:
        await reject(websocket, "Project required", 4403)
        return
    try:
        email = verify_access_token(token)
    except HTTPException:
        await reject(websocket, "Invalid token")
        return

    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not user:
            await reject(websocket, "Invalid token")
            return
        try:
            get_project_access(project_id, user, db)
        except HTTPException:
            await reject(websocket, "Project access required", 4403)
            return
        user_id = user.id

    await manager.connect(project_id, websocket)
    await websocket.send_json({"type": "connection.ready", "project_id": project_id, "user_id": user_id})
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        await manager.disconnect(project_id, websocket)
