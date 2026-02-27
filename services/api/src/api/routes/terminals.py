"""REST endpoints for terminal session lifecycle — proxies to AI service."""

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..database import async_session
from ..guards import get_current_user
from ..models.project import Project

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class CreateTerminalRequest(BaseModel):
    project_id: str | None = None


@router.post("/terminals")
async def create_terminal(req: CreateTerminalRequest):
    """Create a terminal session — resolve cwd and proxy to AI service."""
    if req.project_id:
        async with async_session() as session:
            project = await session.get(Project, uuid.UUID(req.project_id))
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            cwd = project.clone_path
    else:
        cwd = "/data/projects"

    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            f"{settings.ai_service_url}/terminals",
            json={"cwd": cwd},
        )

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()


@router.delete("/terminals/{session_id}")
async def delete_terminal(session_id: str):
    """Destroy a terminal session — proxy to AI service."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.delete(
            f"{settings.ai_service_url}/terminals/{session_id}",
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Terminal session not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()
