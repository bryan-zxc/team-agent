import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from src.api.database import async_session
from src.api.models.room import Room
from src.api.models.chat import Chat
from src.api.models.message import Message
from src.api.models.user import User

router = APIRouter()


class CreateRoomRequest(BaseModel):
    name: str


@router.get("/rooms")
async def list_rooms():
    async with async_session() as session:
        rooms = (await session.execute(select(Room).order_by(Room.created_at))).scalars().all()

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


@router.post("/rooms")
async def create_room(req: CreateRoomRequest):
    async with async_session() as session:
        room = Room(name=req.name)
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

        rows = (
            await session.execute(
                select(Message, User.display_name)
                .join(User, Message.user_id == User.id)
                .where(Message.chat_id == primary_chat.id)
                .order_by(Message.created_at)
            )
        ).all()

        return [
            {
                "id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "user_id": str(msg.user_id),
                "display_name": display_name,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg, display_name in rows
        ]
