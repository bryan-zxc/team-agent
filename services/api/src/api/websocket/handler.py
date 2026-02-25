import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from datetime import datetime, timezone

from ..database import async_session
from ..models.chat import Chat
from ..models.message import Message
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.room import Room
from ..models.session import Session
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

            if member and member.type in ("ai", "coordinator"):
                # Typing indicator so users see immediate feedback
                await manager.broadcast(uuid.UUID(chat_id), {
                    "_event": "typing",
                    "member_id": mid,
                    "display_name": member.display_name,
                })
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
    # Validate session cookie
    session_id = websocket.cookies.get("session_id")
    if not session_id:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    async with async_session() as db:
        auth_session = await db.get(Session, session_id)
        if not auth_session or auth_session.expires_at < datetime.now(timezone.utc):
            await websocket.close(code=4001, reason="Invalid or expired session")
            return

        member = await db.get(ProjectMember, member_id)
        if not member or member.user_id != auth_session.user_id:
            await websocket.close(code=4003, reason="Forbidden")
            return

    await manager.connect(chat_id, websocket)

    # Look up display name, type, and owning project
    room_id = None
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        display_name = member.display_name if member else "Unknown"
        member_type = member.type if member else "human"

        chat = await session.get(Chat, chat_id)
        chat_type = chat.type if chat else "primary"
        workload_id = str(chat.workload_id) if chat and chat.workload_id else None

        # Resolve project_id via chat → room for lockdown checks
        project_id = None
        if chat:
            room = await session.get(Room, chat.room_id)
            if room:
                project_id = room.project_id
                room_id = room.id

    # Register room-level connection for status broadcasts
    if room_id:
        manager.connect_room(room_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            # Typing indicator — ephemeral, no persistence
            if data.get("_event") == "typing":
                await manager.broadcast_except(chat_id, {
                    "_event": "typing",
                    "member_id": str(member_id),
                    "display_name": display_name,
                }, exclude=websocket)
                continue

            # Check project lockdown before processing each message
            if project_id:
                async with async_session() as session:
                    project = await session.get(Project, project_id)
                    if project and project.is_locked:
                        await websocket.send_json({
                            "error": "project_locked",
                            "detail": f"Project is locked: {project.lock_reason}",
                        })
                        continue

            # Expect structured format: {"blocks": [...], "mentions": [...], "reply_to_id": ...}
            blocks = data.get("blocks", [])
            mentions = data.get("mentions", [])
            reply_to_id = data.get("reply_to_id")

            if not blocks:
                continue

            # Store full structured JSON as content
            content = json.dumps({"blocks": blocks, "mentions": mentions, "reply_to_id": reply_to_id})

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
                "reply_to_id": reply_to_id,
            }

            # Broadcast to all connections in this chat
            await manager.broadcast(chat_id, msg_data)

            # Route message: workload chats → workload:messages, primary chats → ai:respond
            if chat_type == "workload" and workload_id:
                plain_text = " ".join(
                    b["value"] for b in blocks if b.get("type") == "text"
                )
                await _get_redis().publish(
                    "workload:messages",
                    json.dumps({"workload_id": workload_id, "content": plain_text}),
                )
                logger.info("Published workload message for %s", workload_id[:8])
            elif mentions:
                await _notify_ai_if_mentioned(mentions, str(chat_id))

    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
        if room_id:
            manager.disconnect_room(room_id, websocket)
