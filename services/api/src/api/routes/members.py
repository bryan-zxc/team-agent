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

router = APIRouter(prefix="/members")
logger = logging.getLogger(__name__)


class AddHumanRequest(BaseModel):
    user_id: str


class GenerateAgentRequest(BaseModel):
    name: str | None = None


class UpdateProfileRequest(BaseModel):
    content: str


def _profile_path(member_name: str) -> Path:
    return Path(settings.agents_dir) / settings.project_name / f"{member_name.lower()}.md"


@router.get("")
async def list_members():
    """All project members."""
    async with async_session() as session:
        members = (
            await session.execute(
                select(ProjectMember).order_by(ProjectMember.created_at)
            )
        ).scalars().all()
        return [
            {
                "id": str(m.id),
                "display_name": m.display_name,
                "type": m.type,
            }
            for m in members
        ]


@router.get("/available-users")
async def available_users():
    """Users not yet added as project members."""
    async with async_session() as session:
        existing_user_ids = (
            await session.execute(
                select(ProjectMember.user_id).where(ProjectMember.user_id.isnot(None))
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


@router.post("/human")
async def add_human_member(req: AddHumanRequest):
    """Add a human user as a project member."""
    async with async_session() as session:
        user = await session.get(User, uuid.UUID(req.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        project = (await session.execute(select(Project).limit(1))).scalar_one()

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


@router.post("/ai")
async def generate_ai_member(req: GenerateAgentRequest):
    """Request AI agent generation via the AI service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.ai_service_url}/generate-agent",
                json={
                    "project_name": settings.project_name,
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


@router.get("/{member_id}/profile")
async def get_profile(member_id: uuid.UUID):
    """Read the raw markdown profile for an AI member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type != "ai":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = _profile_path(member.display_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile file not found")

    return {"content": path.read_text()}


@router.put("/{member_id}/profile")
async def update_profile(member_id: uuid.UUID, req: UpdateProfileRequest):
    """Write raw markdown back to the profile file."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type != "ai":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = _profile_path(member.display_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content)

    return {"status": "ok"}
