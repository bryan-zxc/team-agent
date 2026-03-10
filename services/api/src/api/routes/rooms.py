import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..blocks import convert_text_blocks
from ..database import async_session
from ..guards import get_current_user, get_unlocked_project
from ..models.room import Room
from ..models.chat import Chat
from ..models.message import Message
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.user import User
from ..models.workload import Workload
from ..websocket.manager import manager

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class CreateRoomRequest(BaseModel):
    name: str


class RenameRoomRequest(BaseModel):
    name: str


@router.get("/projects/{project_id}/rooms")
async def list_rooms(project_id: uuid.UUID):
    async with async_session() as session:
        rooms = (
            (
                await session.execute(
                    select(Room)
                    .where(Room.project_id == project_id, Room.type == "standard")
                    .order_by(Room.created_at)
                )
            )
            .scalars()
            .all()
        )

        result = []
        for room in rooms:
            primary_chat = (
                await session.execute(
                    select(Chat).where(Chat.room_id == room.id, Chat.type == "primary")
                )
            ).scalar_one_or_none()

            result.append(
                {
                    "id": str(room.id),
                    "name": room.name,
                    "primary_chat_id": str(primary_chat.id) if primary_chat else None,
                    "created_at": room.created_at.isoformat(),
                }
            )

        return result


@router.post("/projects/{project_id}/rooms")
async def create_room(
    req: CreateRoomRequest,
    project: Project = Depends(get_unlocked_project),
):
    async with async_session() as session:
        room = Room(name=req.name, project_id=project.id)
        session.add(room)
        await session.flush()

        chat = Chat(room_id=room.id, type="primary")
        session.add(chat)
        await session.commit()
        await session.refresh(room)
        await session.refresh(chat)

        return {
            "id": str(room.id),
            "name": room.name,
            "primary_chat_id": str(chat.id),
            "created_at": room.created_at.isoformat(),
        }


@router.patch("/projects/{project_id}/rooms/{room_id}")
async def rename_room(
    room_id: uuid.UUID,
    req: RenameRoomRequest,
    project: Project = Depends(get_unlocked_project),
):
    async with async_session() as session:
        room = (
            await session.execute(
                select(Room).where(Room.id == room_id, Room.project_id == project.id)
            )
        ).scalar_one_or_none()

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        room.name = req.name.strip()
        await session.commit()
        await session.refresh(room)

        primary_chat = (
            await session.execute(
                select(Chat).where(Chat.room_id == room.id, Chat.type == "primary")
            )
        ).scalar_one_or_none()

        return {
            "id": str(room.id),
            "name": room.name,
            "primary_chat_id": str(primary_chat.id) if primary_chat else None,
            "created_at": room.created_at.isoformat(),
        }


@router.get("/rooms/{room_id}/messages")
async def get_room_messages(room_id: uuid.UUID):
    async with async_session() as session:
        primary_chat = (
            await session.execute(
                select(Chat).where(Chat.room_id == room_id, Chat.type == "primary")
            )
        ).scalar_one_or_none()

        if not primary_chat:
            return []

        return await _messages_for_chat(session, primary_chat.id)


@router.get("/rooms/{room_id}/workloads")
async def list_workloads(room_id: uuid.UUID):
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Chat, Workload, ProjectMember.display_name)
                .join(Workload, Chat.workload_id == Workload.id)
                .outerjoin(ProjectMember, Workload.member_id == ProjectMember.id)
                .where(Chat.room_id == room_id, Chat.type == "workload")
                .order_by(Chat.created_at)
            )
        ).all()

        return [
            {
                "id": str(chat.id),
                "workload_id": str(workload.id),
                "dispatch_id": workload.dispatch_id,
                "title": workload.title,
                "description": workload.description,
                "status": chat.status,
                "permission_mode": workload.permission_mode,
                "has_session": chat.session_id is not None,
                "owner_name": display_name,
                "owner_id": str(workload.member_id),
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat()
                if chat.updated_at
                else chat.created_at.isoformat(),
            }
            for chat, workload, display_name in rows
        ]


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: uuid.UUID):
    async with async_session() as session:
        return await _messages_for_chat(session, chat_id)


def _extract_reply_to_id(content: str) -> str | None:
    try:
        return json.loads(content).get("reply_to_id")
    except (json.JSONDecodeError, TypeError):
        return None


def _get_redis():
    from ..main import redis_client

    return redis_client


def _extract_plain_text(blocks: list[dict]) -> str:
    """Extract plain text from structured message blocks."""
    return " ".join(b["value"] for b in blocks if b.get("type") == "text")


class PostMessageRequest(BaseModel):
    blocks: list[dict]
    mentions: list[str] = []


@router.post("/chats/{chat_id}/messages")
async def post_message(
    chat_id: uuid.UUID,
    req: PostMessageRequest,
    user: User = Depends(get_current_user),
):
    """Create a message via REST (same semantics as the WebSocket handler)."""
    if not req.blocks:
        raise HTTPException(status_code=400, detail="blocks must not be empty")

    async with async_session() as session:
        # Resolve chat → room → project
        chat = await session.get(Chat, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        room = await session.get(Room, chat.room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        project = await session.get(Project, room.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.is_locked:
            raise HTTPException(
                status_code=403,
                detail=f"Project is locked: {project.lock_reason}",
            )

        # Resolve the user's project member
        member = (
            await session.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == room.project_id,
                    ProjectMember.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this project")

        # Auto-convert @mentions, /skills, and [links]
        blocks = req.blocks
        mentions = req.mentions
        blocks, mentions = await convert_text_blocks(
            blocks, room.project_id, mentions
        )

        content = json.dumps({"blocks": blocks, "mentions": mentions})

        # Persist
        message = Message(
            chat_id=chat_id,
            member_id=member.id,
            content=content,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

    msg_data = {
        "id": str(message.id),
        "chat_id": str(chat_id),
        "member_id": str(member.id),
        "display_name": member.display_name,
        "type": member.type,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "reply_to_id": None,
    }

    # Broadcast to all WebSocket connections in this chat
    await manager.broadcast(chat_id, msg_data)

    # Route to Redis (same logic as WS handler)
    if chat.type in ("workload", "admin"):
        plain_text = _extract_plain_text(blocks)
        await _get_redis().publish(
            "chat:messages",
            json.dumps({"chat_id": str(chat_id), "content": plain_text}),
        )
        logger.info("REST: published %s message for chat %s", chat.type, str(chat_id)[:8])

    return msg_data


async def _messages_for_chat(session, chat_id: uuid.UUID):
    rows = (
        await session.execute(
            select(Message, ProjectMember.display_name, ProjectMember.type)
            .join(ProjectMember, Message.member_id == ProjectMember.id)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
        )
    ).all()

    return [
        {
            "id": str(msg.id),
            "chat_id": str(msg.chat_id),
            "member_id": str(msg.member_id),
            "display_name": display_name,
            "type": member_type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "reply_to_id": _extract_reply_to_id(msg.content),
        }
        for msg, display_name, member_type in rows
    ]
