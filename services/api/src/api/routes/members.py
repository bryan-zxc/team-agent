import logging
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class AddHumanRequest(BaseModel):
    user_id: str


class GenerateAgentRequest(BaseModel):
    name: str | None = None


class UpdateProfileRequest(BaseModel):
    content: str


async def _resolve_profile_path(member: ProjectMember) -> Path:
    """Resolve the markdown profile path for an AI member via its project's clone_path."""
    from ..database import async_session as _session
    async with _session() as session:
        project = await session.get(Project, member.project_id)
    if not project or not project.clone_path:
        raise HTTPException(status_code=404, detail="Project not found or has no clone_path")
    return Path(project.clone_path) / ".agent" / f"{member.display_name.lower()}.md"


@router.get("/projects/{project_id}/members")
async def list_members(project_id: uuid.UUID):
    async with async_session() as session:
        members = (
            await session.execute(
                select(ProjectMember)
                .where(ProjectMember.project_id == project_id)
                .order_by(ProjectMember.created_at)
            )
        ).scalars().all()
        return [
            {
                "id": str(m.id),
                "display_name": m.display_name,
                "type": m.type,
                "user_id": str(m.user_id) if m.user_id else None,
            }
            for m in members
        ]


@router.get("/projects/{project_id}/available-users")
async def available_users(project_id: uuid.UUID):
    """Users not yet added as members of this project."""
    async with async_session() as session:
        existing_user_ids = (
            await session.execute(
                select(ProjectMember.user_id).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id.isnot(None),
                )
            )
        ).scalars().all()

        query = select(User).order_by(User.display_name)
        if existing_user_ids:
            query = query.where(User.id.notin_(existing_user_ids))

        users = (await session.execute(query)).scalars().all()
        return [
            {"id": str(u.id), "display_name": u.display_name}
            for u in users
        ]


@router.post("/projects/{project_id}/members/human")
async def add_human_member(project_id: uuid.UUID, req: AddHumanRequest):
    async with async_session() as session:
        user = await session.get(User, uuid.UUID(req.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        member = ProjectMember(
            project_id=project_id,
            user_id=user.id,
            display_name=user.display_name,
            type="human",
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        return {
            "id": str(member.id),
            "display_name": member.display_name,
            "type": member.type,
        }


@router.post("/projects/{project_id}/members/ai")
async def generate_ai_member(project_id: uuid.UUID, req: GenerateAgentRequest):
    """Request AI agent generation via the AI service."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        project_name = project.name

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.ai_service_url}/generate-agent",
                json={
                    "project_name": project_name,
                    "name": req.name,
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Agent generation timed out")
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail="AI service unavailable")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Agent generation failed"))

    return resp.json()


@router.get("/members/{member_id}/profile")
async def get_profile(member_id: uuid.UUID):
    """Read the raw markdown profile for an AI member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = await _resolve_profile_path(member)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile file not found")

    return {"content": path.read_text()}


@router.put("/members/{member_id}/profile")
async def update_profile(member_id: uuid.UUID, req: UpdateProfileRequest):
    """Write raw markdown back to the profile file."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = await _resolve_profile_path(member)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content)

    return {"status": "ok"}
