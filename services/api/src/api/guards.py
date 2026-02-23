"""Reusable endpoint guards as FastAPI dependencies."""

import uuid

from fastapi import HTTPException

from .database import async_session
from .models.project import Project


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
