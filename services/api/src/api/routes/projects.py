import asyncio
import logging
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
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
from ..guards import get_current_user
from ..models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)

CLONE_BASE = Path("/data/projects")


class CreateProjectRequest(BaseModel):
    name: str
    git_repo_url: str
    default_branch: str | None = None


class UpdateProjectRequest(BaseModel):
    default_branch: str


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
                "default_branch": p.default_branch,
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
            "default_branch": project.default_branch,
            "is_locked": project.is_locked,
            "lock_reason": project.lock_reason,
            "created_at": project.created_at.isoformat(),
        }


@router.post("/projects")
async def create_project(req: CreateProjectRequest, creator: User = Depends(get_current_user)):
    async with async_session() as session:
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

        clone_args = ["git", "clone"]
        if req.default_branch:
            clone_args += ["--branch", req.default_branch]
        clone_args += [req.git_repo_url, clone_path]

        proc = await asyncio.create_subprocess_exec(
            *clone_args,
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

        # Read the actual checked-out branch and store it
        branch_proc = await asyncio.create_subprocess_exec(
            "git", "symbolic-ref", "--short", "HEAD",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        branch_out, _ = await branch_proc.communicate()
        if branch_proc.returncode == 0:
            project.default_branch = branch_out.decode().strip()

        logger.info("Cloned %s to %s (branch: %s)", req.git_repo_url, clone_path, project.default_branch)

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
        "default_branch": project.default_branch,
        "is_locked": False,
        "lock_reason": None,
        "created_at": project.created_at.isoformat(),
        "creator_member_id": str(creator_member.id),
        "zimomo": zimomo_member,
    }


@router.patch("/projects/{project_id}")
async def update_project(project_id: uuid.UUID, req: UpdateProjectRequest):
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project not found")

        clone_path = project.clone_path

        # Fetch latest refs from remote
        fetch_proc = await asyncio.create_subprocess_exec(
            "git", "fetch", "origin",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await fetch_proc.communicate()

        # Validate branch exists on remote
        check_proc = await asyncio.create_subprocess_exec(
            "git", "branch", "-r", "--list", f"origin/{req.default_branch}",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        check_out, _ = await check_proc.communicate()
        if not check_out.decode().strip():
            raise HTTPException(
                status_code=422,
                detail=f"Branch '{req.default_branch}' does not exist on remote",
            )

        # Checkout the branch
        checkout_proc = await asyncio.create_subprocess_exec(
            "git", "checkout", req.default_branch,
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, checkout_err = await checkout_proc.communicate()
        if checkout_proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to switch branch: {checkout_err.decode().strip()}",
            )

        # Pull latest changes for the branch
        pull_proc = await asyncio.create_subprocess_exec(
            "git", "pull", "origin", req.default_branch,
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await pull_proc.communicate()

        project.default_branch = req.default_branch
        await session.commit()
        await session.refresh(project)

        logger.info("Switched project %s to branch %s", project.name, req.default_branch)

        return {
            "id": str(project.id),
            "name": project.name,
            "git_repo_url": project.git_repo_url,
            "clone_path": project.clone_path,
            "default_branch": project.default_branch,
            "is_locked": project.is_locked,
            "lock_reason": project.lock_reason,
            "created_at": project.created_at.isoformat(),
        }


@router.get("/projects/{project_id}/branches")
async def list_branches(project_id: uuid.UUID):
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project not found")

        clone_path = project.clone_path

        # Fetch latest refs
        fetch_proc = await asyncio.create_subprocess_exec(
            "git", "fetch", "origin",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await fetch_proc.communicate()

        # List remote branches
        proc = await asyncio.create_subprocess_exec(
            "git", "branch", "-r", "--format=%(refname:short)",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        branches = []
        for line in stdout.decode().strip().splitlines():
            line = line.strip()
            if line.startswith("origin/") and line != "origin/HEAD":
                branches.append(line.removeprefix("origin/"))

        # Current branch
        head_proc = await asyncio.create_subprocess_exec(
            "git", "symbolic-ref", "--short", "HEAD",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        head_out, _ = await head_proc.communicate()
        current = head_out.decode().strip() if head_proc.returncode == 0 else None

        return {
            "branches": sorted(branches),
            "current": current,
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
