import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ..database import async_session
from ..models.message import Message
from ..models.project_member import ProjectMember
from .manager import manager

router = APIRouter()


def _get_redis():
    from ..main import redis_client
    return redis_client


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
):
    await manager.connect(chat_id, websocket)

    # Look up display name from project_members
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        display_name = member.display_name if member else "Unknown"

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "")
            if not content:
                continue

            # Persist message
            message = Message(
                chat_id=chat_id,
                member_id=member_id,
                content=content,
            )
            async with async_session() as session:
                session.add(message)
                await session.commit()
                await session.refresh(message)

            msg_data = {
                "id": str(message.id),
                "chat_id": str(chat_id),
                "member_id": str(member_id),
                "display_name": display_name,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            # Broadcast to all connections in this chat
            await manager.broadcast(chat_id, msg_data)

            # Publish to Redis for AI service
            await _get_redis().publish("chat:messages", json.dumps(msg_data))

    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
