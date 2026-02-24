"""Reusable endpoint guards as FastAPI dependencies."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from .database import async_session
from .models.project import Project
from .models.session import Session
from .models.user import User


async def get_current_user(request: Request) -> User:
    """Validate the session cookie and return the authenticated User."""
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
