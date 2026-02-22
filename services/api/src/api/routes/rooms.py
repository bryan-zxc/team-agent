import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..database import async_session
from ..models.room import Room
from ..models.chat import Chat
from ..models.message import Message
from ..models.project_member import ProjectMember

router = APIRouter()


class CreateRoomRequest(BaseModel):
    name: str


class RenameRoomRequest(BaseModel):
    name: str


@router.get("/projects/{project_id}/rooms")
async def list_rooms(project_id: uuid.UUID):
    async with async_session() as session:
        rooms = (
            await session.execute(
                select(Room)
                .where(Room.project_id == project_id)
                .order_by(Room.created_at)
            )
        ).scalars().all()

        result = []
        for room in rooms:
            primary_chat = (
                await session.execute(
                    select(Chat).where(Chat.room_id == room.id, Chat.type == "primary")
                )
            ).scalar_one_or_none()

            result.append({
                "id": str(room.id),
                "name": room.name,
                "primary_chat_id": str(primary_chat.id) if primary_chat else None,
                "created_at": room.created_at.isoformat(),
            })

        return result


@router.post("/projects/{project_id}/rooms")
async def create_room(project_id: uuid.UUID, req: CreateRoomRequest):
    async with async_session() as session:
        room = Room(name=req.name, project_id=project_id)
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
async def rename_room(project_id: uuid.UUID, room_id: uuid.UUID, req: RenameRoomRequest):
    async with async_session() as session:
        room = (
            await session.execute(
                select(Room).where(Room.id == room_id, Room.project_id == project_id)
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
                select(Chat, ProjectMember.display_name)
                .outerjoin(ProjectMember, Chat.owner_id == ProjectMember.id)
                .where(Chat.room_id == room_id, Chat.type == "workload")
                .order_by(Chat.created_at)
            )
        ).all()

        return [
            {
                "id": str(chat.id),
                "title": chat.title,
                "owner_name": display_name,
                "owner_id": str(chat.owner_id) if chat.owner_id else None,
                "created_at": chat.created_at.isoformat(),
            }
            for chat, display_name in rows
        ]


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: uuid.UUID):
    async with async_session() as session:
        return await _messages_for_chat(session, chat_id)


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
        }
        for msg, display_name, member_type in rows
    ]
