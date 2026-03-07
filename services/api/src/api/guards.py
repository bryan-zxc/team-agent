"""Reusable endpoint guards as FastAPI dependencies."""

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from .database import async_session
from .models.project import Project
from .models.project_member import ProjectMember
from .models.session import Session
from .models.user import User


async def get_current_user(request: Request) -> User:
    """Validate the session cookie and return the authenticated User.

    Also accepts an X-Internal-Key header for service-to-service calls
    from the AI service — returns a sentinel User so downstream code
    still receives a User object.
    """
    from .config import settings

    internal_key = request.headers.get("x-internal-key")
    if internal_key and internal_key == settings.internal_api_key:
        return User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            email="internal@team-agent.local",
            display_name="Internal Service",
        )

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with async_session() as db:
        session = await db.get(Session, session_id)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")
        if session.expires_at < datetime.now(timezone.utc):
            await db.delete(session)
            await db.commit()
            raise HTTPException(status_code=401, detail="Session expired")

        user = await db.get(User, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user


async def get_unlocked_project(project_id: uuid.UUID) -> Project:
    """Load a project and verify it is not locked.

    Use as a FastAPI dependency to fold the lock check into the project
    lookup the endpoint was already going to make — zero extra latency.
    """
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.is_locked:
            raise HTTPException(
                status_code=403,
                detail=f"Project is locked: {project.lock_reason}",
            )
        return project


async def require_project_member(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> User:
    """Verify the current user is a member of the project.

    The internal service user (all-zero UUID) bypasses the check so that
    AI-service calls via X-Internal-Key still work.
    """
    if user.id == uuid.UUID("00000000-0000-0000-0000-000000000000"):
        return user

    async with async_session() as session:
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
        member = (await session.execute(stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this project")
    return user
