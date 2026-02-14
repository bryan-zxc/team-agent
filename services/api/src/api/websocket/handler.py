import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from src.api.database import async_session
from src.api.models.message import Message
from src.api.models.user import User
from src.api.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
):
    await manager.connect(chat_id, websocket)

    # Look up display name for this user
    async with async_session() as session:
        user = await session.get(User, user_id)
        display_name = user.display_name if user else "Unknown"

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "")
            if not content:
                continue

            # Persist message
            message = Message(
                chat_id=chat_id,
                user_id=user_id,
                content=content,
            )
            async with async_session() as session:
                session.add(message)
                await session.commit()
                await session.refresh(message)

            # Broadcast to all connections in this chat
            await manager.broadcast(chat_id, {
                "id": str(message.id),
                "chat_id": str(chat_id),
                "user_id": str(user_id),
                "display_name": display_name,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
