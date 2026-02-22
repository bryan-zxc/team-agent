import asyncio
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
from ..models.room import Room
from ..models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

CLONE_BASE = Path("/data/projects")


class CreateProjectRequest(BaseModel):
    name: str
    git_repo_url: str
    creator_user_id: str


@router.get("/projects")
async def list_projects():
    async with async_session() as session:
        projects = (
            await session.execute(select(Project).order_by(Project.created_at))
        ).scalars().all()

        result = []
        for p in projects:
            member_count = len(
                (
                    await session.execute(
                        select(ProjectMember).where(ProjectMember.project_id == p.id)
                    )
                ).scalars().all()
            )
            room_count = len(
                (
                    await session.execute(
                        select(Room).where(Room.project_id == p.id)
                    )
                ).scalars().all()
            )
            result.append({
                "id": str(p.id),
                "name": p.name,
                "git_repo_url": p.git_repo_url,
                "member_count": member_count,
                "room_count": room_count,
                "created_at": p.created_at.isoformat(),
            })

        return result


@router.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID):
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {
            "id": str(project.id),
            "name": project.name,
            "git_repo_url": project.git_repo_url,
            "clone_path": project.clone_path,
            "created_at": project.created_at.isoformat(),
        }


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    async with async_session() as session:
        # Validate creator exists
        creator = await session.get(User, uuid.UUID(req.creator_user_id))
        if not creator:
            raise HTTPException(status_code=404, detail="Creator user not found")

        # Check name uniqueness
        existing = (
            await session.execute(select(Project).where(Project.name == req.name))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Project name already exists")

        # Create project
        project = Project(
            name=req.name,
            git_repo_url=req.git_repo_url,
        )
        session.add(project)
        await session.flush()

        # Clone repo
        clone_path = str(CLONE_BASE / str(project.id) / "repo")
        Path(clone_path).parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", req.git_repo_url, clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"Git clone failed: {stderr.decode().strip()}",
            )

        project.clone_path = clone_path
        logger.info("Cloned %s to %s", req.git_repo_url, clone_path)

        # Create agents directory
        agents_dir = Path(settings.agents_dir) / req.name
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Add creator as human member
        creator_member = ProjectMember(
            project_id=project.id,
            user_id=creator.id,
            display_name=creator.display_name,
            type="human",
        )
        session.add(creator_member)

        await session.commit()
        await session.refresh(project)
        await session.refresh(creator_member)

    # Generate Zimomo via AI service (outside the DB transaction)
    zimomo_member = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ai_service_url}/generate-agent",
                json={"project_name": req.name, "name": "Zimomo", "member_type": "coordinator"},
            )
        if resp.status_code == 200:
            zimomo_member = resp.json()
            logger.info("Generated Zimomo for project %s", req.name)
        else:
            logger.warning("Zimomo generation failed: %s", resp.text)
    except Exception as e:
        logger.warning("Zimomo generation error: %s", e)

    return {
        "id": str(project.id),
        "name": project.name,
        "git_repo_url": project.git_repo_url,
        "clone_path": project.clone_path,
        "created_at": project.created_at.isoformat(),
        "creator_member_id": str(creator_member.id),
        "zimomo": zimomo_member,
    }
