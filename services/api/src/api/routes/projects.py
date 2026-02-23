import asyncio
import logging
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..database import async_session
from ..manifest import (
    ManifestStatus,
    check_unclaimed,
    validate_manifest,
    write_manifest,
)
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
                "is_locked": p.is_locked,
                "lock_reason": p.lock_reason,
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
            "is_locked": project.is_locked,
            "lock_reason": project.lock_reason,
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

        # Check if repo is already claimed by another project
        claim_check = check_unclaimed(clone_path)
        if claim_check.status == ManifestStatus.CLAIMED_PROD:
            shutil.rmtree(Path(clone_path).parent)
            raise HTTPException(status_code=409, detail=claim_check.reason)
        if claim_check.status == ManifestStatus.CLAIMED_OTHER:
            shutil.rmtree(Path(clone_path).parent)
            raise HTTPException(status_code=409, detail=claim_check.reason)

        # Create .team-agent/agents/ directory and write manifest
        (Path(clone_path) / ".team-agent" / "agents").mkdir(parents=True, exist_ok=True)
        write_manifest(
            clone_path,
            project_id=str(project.id),
            project_name=req.name,
            env=settings.team_agent_env,
        )

        # Add creator as human member
        creator_member = ProjectMember(
            project_id=project.id,
            user_id=creator.id,
            display_name=creator.display_name,
            type="human",
        )
        session.add(creator_member)

        try:
            await session.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="A project with this git repository URL already exists.",
            )
        await session.refresh(project)
        await session.refresh(creator_member)

    # Generate Zimomo via AI service (outside the DB transaction)
    # This also triggers git commit+push of the manifest and Zimomo profile together
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
        "is_locked": False,
        "lock_reason": None,
        "created_at": project.created_at.isoformat(),
        "creator_member_id": str(creator_member.id),
        "zimomo": zimomo_member,
    }


@router.post("/projects/{project_id}/check-manifest")
async def check_manifest_endpoint(project_id: uuid.UUID, pull: bool = True):
    """Validate manifest ownership.

    Used by: frontend refresh button (pull=true), project entry (pull=true),
    AI service post-workload check (pull=false).
    """
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project not found")

        result = await validate_manifest(
            project.clone_path,
            str(project.id),
            project.name,
            settings.team_agent_env,
            pull=pull,
        )

        if result.status == ManifestStatus.LOCKED:
            project.is_locked = True
            project.lock_reason = result.reason
            await session.commit()
        elif result.status in (ManifestStatus.VALID, ManifestStatus.CORRECTED):
            if project.is_locked:
                project.is_locked = False
                project.lock_reason = None
                await session.commit()

        return {
            "status": result.status.value,
            "manifest": result.manifest,
            "reason": result.reason,
            "is_locked": project.is_locked,
        }
