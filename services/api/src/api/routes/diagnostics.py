import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select

from ..config import memory_handler
from ..database import async_session
from ..models.chat import Chat
from ..models.message import Message
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.room import Room
from ..models.workload import Workload

router = APIRouter(prefix="/diagnostics")


@router.get("/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="Filter by log level (e.g. ERROR, WARNING)"),
    limit: int = Query(100, ge=1, le=1000),
    since: Optional[datetime] = Query(None, description="ISO 8601 timestamp lower bound"),
):
    """Return recent application logs from the in-memory ring buffer."""
    return memory_handler.get_records(level=level, limit=limit, since=since)


@router.get("/rooms")
async def list_rooms(
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
):
    """List rooms with basic metadata."""
    async with async_session() as session:
        stmt = select(Room, Project.name.label("project_name")).join(
            Project, Room.project_id == Project.id
        )
        if project_id:
            stmt = stmt.where(Room.project_id == project_id)
        stmt = stmt.order_by(desc(Room.created_at))

        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(room.id),
            "name": room.name,
            "type": room.type,
            "project_id": str(room.project_id),
            "project_name": project_name,
            "created_at": room.created_at.isoformat(),
        }
        for room, project_name in rows
    ]


@router.get("/chats")
async def list_chats(
    status: Optional[str] = Query(None, description="Filter by status (e.g. running, investigating, completed)"),
    room_id: Optional[uuid.UUID] = Query(None, description="Filter by room ID"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    type: Optional[str] = Query(None, description="Filter by chat type (e.g. primary, workload, admin)"),
    limit: int = Query(50, ge=1, le=200),
):
    """List chats with filtering. Returns chat records with room name, owner name, and workload title."""
    async with async_session() as session:
        stmt = (
            select(
                Chat,
                Room.name.label("room_name"),
                Room.type.label("room_type"),
                ProjectMember.display_name.label("owner_name"),
                Workload.title.label("workload_title"),
            )
            .join(Room, Chat.room_id == Room.id)
            .outerjoin(ProjectMember, Chat.owner_id == ProjectMember.id)
            .outerjoin(Workload, Chat.workload_id == Workload.id)
        )

        if status:
            stmt = stmt.where(Chat.status == status)
        if room_id:
            stmt = stmt.where(Chat.room_id == room_id)
        if project_id:
            stmt = stmt.where(Room.project_id == project_id)
        if type:
            stmt = stmt.where(Chat.type == type)

        stmt = stmt.order_by(desc(Chat.created_at)).limit(limit)
        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(chat.id),
            "room_id": str(chat.room_id),
            "room_name": room_name,
            "room_type": room_type,
            "type": chat.type,
            "title": chat.title,
            "status": chat.status,
            "owner_name": owner_name,
            "workload_title": workload_title,
            "permission_mode": chat.permission_mode,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        }
        for chat, room_name, room_type, owner_name, workload_title in rows
    ]


@router.get("/chats/{chat_id}")
async def get_chat_diagnostics(
    chat_id: uuid.UUID,
    message_limit: int = Query(20, ge=1, le=200),
):
    """Return a rich debugging view of a chat and its related entities."""
    async with async_session() as session:
        chat = (
            await session.execute(select(Chat).where(Chat.id == chat_id))
        ).scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        room = (
            await session.execute(select(Room).where(Room.id == chat.room_id))
        ).scalar_one_or_none()

        project = None
        if room:
            project = (
                await session.execute(select(Project).where(Project.id == room.project_id))
            ).scalar_one_or_none()

        owner = None
        if chat.owner_id:
            owner = (
                await session.execute(
                    select(ProjectMember).where(ProjectMember.id == chat.owner_id)
                )
            ).scalar_one_or_none()

        workload = None
        if chat.workload_id:
            workload = (
                await session.execute(
                    select(Workload).where(Workload.id == chat.workload_id)
                )
            ).scalar_one_or_none()

        rows = (
            await session.execute(
                select(Message, ProjectMember.display_name, ProjectMember.type)
                .join(ProjectMember, Message.member_id == ProjectMember.id)
                .where(Message.chat_id == chat_id)
                .order_by(desc(Message.created_at))
                .limit(message_limit)
            )
        ).all()

        messages = [
            {
                "id": str(msg.id),
                "member_id": str(msg.member_id),
                "display_name": display_name,
                "member_type": member_type,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg, display_name, member_type in reversed(rows)
        ]

    return {
        "chat": {
            "id": str(chat.id),
            "room_id": str(chat.room_id),
            "type": chat.type,
            "title": chat.title,
            "owner_id": str(chat.owner_id) if chat.owner_id else None,
            "workload_id": str(chat.workload_id) if chat.workload_id else None,
            "session_id": chat.session_id,
            "status": chat.status,
            "permission_mode": chat.permission_mode,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        },
        "room": {
            "id": str(room.id),
            "name": room.name,
            "type": room.type,
            "created_at": room.created_at.isoformat(),
        } if room else None,
        "project": {
            "id": str(project.id),
            "name": project.name,
            "git_repo_url": project.git_repo_url,
            "clone_path": project.clone_path,
            "default_branch": project.default_branch,
            "is_locked": project.is_locked,
        } if project else None,
        "owner": {
            "id": str(owner.id),
            "display_name": owner.display_name,
            "type": owner.type,
        } if owner else None,
        "workload": {
            "id": str(workload.id),
            "main_chat_id": str(workload.main_chat_id),
            "member_id": str(workload.member_id),
            "title": workload.title,
            "description": workload.description,
            "worktree_branch": workload.worktree_branch,
            "dispatch_id": workload.dispatch_id,
            "permission_mode": workload.permission_mode,
            "created_at": workload.created_at.isoformat(),
        } if workload else None,
        "messages": messages,
        "message_count": len(messages),
    }
