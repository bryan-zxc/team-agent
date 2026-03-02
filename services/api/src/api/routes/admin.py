import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..database import async_session
from ..guards import get_current_user
from ..models.chat import Chat
from ..models.project_member import ProjectMember
from ..models.room import Room

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class CreateAdminChatRequest(BaseModel):
    permission_mode: str = "acceptEdits"
    title: str | None = None


@router.get("/projects/{project_id}/admin-room")
async def get_admin_room(project_id: uuid.UUID):
    """Get or create the admin room for a project. Returns room + admin chats."""
    async with async_session() as session:
        room = (
            await session.execute(
                select(Room).where(Room.project_id == project_id, Room.type == "admin")
            )
        ).scalar_one_or_none()

        if not room:
            room = Room(project_id=project_id, name="Admin", type="admin")
            session.add(room)
            await session.commit()
            await session.refresh(room)

        rows = (
            await session.execute(
                select(Chat, ProjectMember.display_name)
                .outerjoin(ProjectMember, Chat.owner_id == ProjectMember.id)
                .where(Chat.room_id == room.id, Chat.type == "admin")
                .order_by(Chat.created_at)
            )
        ).all()

        chats = [
            {
                "id": str(chat.id),
                "title": chat.title,
                "status": chat.status,
                "permission_mode": chat.permission_mode or "default",
                "has_session": chat.session_id is not None,
                "owner_name": display_name,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat() if chat.updated_at else chat.created_at.isoformat(),
            }
            for chat, display_name in rows
        ]

        return {
            "id": str(room.id),
            "name": room.name,
            "chats": chats,
        }


@router.post("/projects/{project_id}/admin-room/chats", status_code=201)
async def create_admin_chat(project_id: uuid.UUID, req: CreateAdminChatRequest = CreateAdminChatRequest()):
    """Create a new admin chat in the project's admin room."""
    async with async_session() as session:
        room = (
            await session.execute(
                select(Room).where(Room.project_id == project_id, Room.type == "admin")
            )
        ).scalar_one_or_none()

        if not room:
            room = Room(project_id=project_id, name="Admin", type="admin")
            session.add(room)
            await session.flush()

        coordinator = (
            await session.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.type == "coordinator",
                )
            )
        ).scalar_one_or_none()

        if not coordinator:
            raise HTTPException(status_code=404, detail="No coordinator found for project")

        now = datetime.now(timezone.utc)
        chat = Chat(
            room_id=room.id,
            type="admin",
            owner_id=coordinator.id,
            status="running",
            permission_mode=req.permission_mode,
            title=req.title,
            updated_at=now,
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        return {
            "id": str(chat.id),
            "room_id": str(room.id),
            "status": chat.status,
            "permission_mode": chat.permission_mode,
            "created_at": chat.created_at.isoformat(),
        }


