import logging
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..guards import get_current_user, get_unlocked_project
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class AddHumanRequest(BaseModel):
    user_id: str


class GenerateAgentRequest(BaseModel):
    name: str | None = None


class UpdateProfileRequest(BaseModel):
    content: str


def _profile_path(clone_path: str, display_name: str) -> Path:
    """Compute the markdown profile path for an AI member."""
    return Path(clone_path) / ".team-agent" / "agents" / f"{display_name.lower()}.md"


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
async def add_human_member(
    req: AddHumanRequest,
    project: Project = Depends(get_unlocked_project),
):
    async with async_session() as session:
        user = await session.get(User, uuid.UUID(req.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        member = ProjectMember(
            project_id=project.id,
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
async def generate_ai_member(
    req: GenerateAgentRequest,
    project: Project = Depends(get_unlocked_project),
):
    """Request AI agent generation via the AI service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.ai_service_url}/generate-agent",
                json={
                    "project_name": project.name,
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


@router.get("/projects/{project_id}/members/{member_id}/profile")
async def get_profile(project_id: uuid.UUID, member_id: uuid.UUID):
    """Read the raw markdown profile for an AI member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project has no cloned repo")

    path = _profile_path(project.clone_path, member.display_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile file not found")

    return {"content": path.read_text()}


@router.put("/projects/{project_id}/members/{member_id}/profile")
async def update_profile(
    member_id: uuid.UUID,
    req: UpdateProfileRequest,
    project: Project = Depends(get_unlocked_project),
):
    """Write raw markdown back to the profile file."""
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project.id:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = _profile_path(project.clone_path, member.display_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content)

    return {"status": "ok"}
