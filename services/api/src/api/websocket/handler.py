import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ..database import async_session
from ..models.message import Message
from ..models.project_member import ProjectMember
from .manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_redis():
    from ..main import redis_client
    return redis_client


async def _notify_ai_if_mentioned(mentions: list[str], chat_id: str):
    """Binary check: if any mentioned member is AI, publish one ai:respond event."""
    async with async_session() as session:
        for mid in mentions:
            try:
                member = await session.get(ProjectMember, uuid.UUID(mid))
            except ValueError:
                continue

            if member and member.type == "ai":
                await _get_redis().publish(
                    "ai:respond", json.dumps({"chat_id": chat_id})
                )
                logger.info("Published ai:respond for chat %s", chat_id[:8])
                return  # One publish per message, regardless of how many AI mentioned


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
):
    await manager.connect(chat_id, websocket)

    # Look up display name and type from project_members
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        display_name = member.display_name if member else "Unknown"
        member_type = member.type if member else "human"

    try:
        while True:
            data = await websocket.receive_json()

            # Expect structured format: {"blocks": [...], "mentions": [...]}
            blocks = data.get("blocks", [])
            mentions = data.get("mentions", [])

            if not blocks:
                continue

            # Store full structured JSON as content
            content = json.dumps({"blocks": blocks, "mentions": mentions})

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
                "type": member_type,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            # Broadcast to all connections in this chat
            await manager.broadcast(chat_id, msg_data)

            # Check if any mentioned members are AI — publish one ai:respond
            if mentions:
                await _notify_ai_if_mentioned(mentions, str(chat_id))

    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
