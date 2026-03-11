import asyncio
import json
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
from ..github import GitHubError, create_repo
from ..board import GH_BIN, provision_board
from ..manifest import (
    read_manifest,
    ManifestStatus,
    check_unclaimed,
    git_commit_and_push,
    update_manifest_board,
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
PROJECT_TEMPLATE = Path(__file__).resolve().parents[3] / "project-template"


class CreateProjectRequest(BaseModel):
    name: str
    git_repo_url: str | None = None
    default_branch: str | None = None


class UpdateProjectRequest(BaseModel):
    default_branch: str


@router.get("/projects")
async def list_projects():
    async with async_session() as session:
        projects = (
            (await session.execute(select(Project).order_by(Project.created_at)))
            .scalars()
            .all()
        )

        result = []
        for p in projects:
            member_count = len(
                (
                    await session.execute(
                        select(ProjectMember).where(ProjectMember.project_id == p.id)
                    )
                )
                .scalars()
                .all()
            )
            room_count = len(
                (await session.execute(select(Room).where(Room.project_id == p.id)))
                .scalars()
                .all()
            )
            result.append(
                {
                    "id": str(p.id),
                    "name": p.name,
                    "git_repo_url": p.git_repo_url,
                    "default_branch": p.default_branch,
                    "member_count": member_count,
                    "room_count": room_count,
                    "is_locked": p.is_locked,
                    "lock_reason": p.lock_reason,
                    "created_at": p.created_at.isoformat(),
                }
            )

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


async def _init_and_push_repo(clone_path: str, clone_url: str) -> None:
    """Initialise a git repo, commit the scaffold, and push to remote."""
    token = settings.github_token
    # Use token-embedded URL for push, then reset to clean URL
    if token:
        parts = clone_url.split("://", 1)
        push_url = f"{parts[0]}://{token}@{parts[1]}" if len(parts) == 2 else clone_url
    else:
        push_url = clone_url

    cmds = [
        ["git", "init"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Team Agent",
            "-c",
            "user.email=agent@team-agent",
            "commit",
            "-m",
            "Initial project scaffold",
        ],
        ["git", "branch", "-M", "main"],
        ["git", "remote", "add", "origin", push_url],
        ["git", "push", "-u", "origin", "main"],
    ]
    for cmd in cmds:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            # Sanitise: strip any token from URLs that git may echo
            if token:
                err_msg = err_msg.replace(token, "***")
            raise HTTPException(
                status_code=422,
                detail=f"Git init failed ({' '.join(cmd[:2])}): {err_msg}",
            )

    # Reset remote URL to clean version (no token)
    await asyncio.create_subprocess_exec(
        "git",
        "remote",
        "set-url",
        "origin",
        clone_url,
        cwd=clone_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


@router.post("/projects")
async def create_project(
    req: CreateProjectRequest, creator: User = Depends(get_current_user)
):
    async with async_session() as session:
        # Check name uniqueness
        existing = (
            await session.execute(select(Project).where(Project.name == req.name))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Project name already exists")

        creating_new = not req.git_repo_url

        # If no URL provided, create a GitHub repo
        git_repo_url = req.git_repo_url
        if creating_new:
            try:
                git_repo_url = await create_repo(req.name)
            except GitHubError as e:
                raise HTTPException(status_code=e.status_code, detail=e.detail)

        # Create project
        project = Project(
            name=req.name,
            git_repo_url=git_repo_url,
        )
        session.add(project)
        await session.flush()

        clone_path = str(CLONE_BASE / str(project.id) / "repo")
        Path(clone_path).parent.mkdir(parents=True, exist_ok=True)

        # Provision project database
        db_dir = Path(clone_path).parent / "databases"
        db_dir.mkdir(parents=True, exist_ok=True)
        import duckdb as _duckdb

        _conn = _duckdb.connect(db_dir / "data.duckdb")
        _conn.close()

        if creating_new:
            # Copy template scaffold and initialise repo
            shutil.copytree(str(PROJECT_TEMPLATE), clone_path)

            # Set up Python environment via uv
            uv_proc = await asyncio.create_subprocess_exec(
                "uv",
                "sync",
                cwd=clone_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, uv_stderr = await uv_proc.communicate()
            if uv_proc.returncode != 0:
                logger.warning("uv sync failed: %s", uv_stderr.decode().strip())
            else:
                logger.info("Ran uv sync for project %s", req.name)

            # Create .team-agent/agents/ directory and write manifest
            (Path(clone_path) / ".team-agent" / "agents").mkdir(
                parents=True, exist_ok=True
            )
            write_manifest(
                clone_path,
                project_id=str(project.id),
                project_name=req.name,
                env=settings.team_agent_env,
            )

            assert git_repo_url
            await _init_and_push_repo(clone_path, git_repo_url)
            project.clone_path = clone_path
            project.default_branch = "main"
            logger.info("Created new repo for %s at %s", req.name, git_repo_url)

            # Board provisioning (non-critical)
            try:
                board_config = await provision_board(req.name, req.name)
                if board_config:
                    update_manifest_board(clone_path, board_config.to_dict())
                    await git_commit_and_push(
                        clone_path,
                        "chore: add board configuration",
                    )
                    logger.info(
                        "Provisioned board %d for project %s",
                        board_config.project_number,
                        req.name,
                    )
            except Exception:
                logger.warning(
                    "Board provisioning failed (non-critical)",
                    exc_info=True,
                )
        else:
            # Clone existing repo
            clone_args = ["git", "clone"]
            if req.default_branch:
                clone_args += ["--branch", req.default_branch]
            clone_args += [git_repo_url, clone_path]

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

            # Set up Python environment if pyproject.toml exists
            if (Path(clone_path) / "pyproject.toml").exists():
                uv_proc = await asyncio.create_subprocess_exec(
                    "uv",
                    "sync",
                    cwd=clone_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, uv_stderr = await uv_proc.communicate()
                if uv_proc.returncode != 0:
                    logger.warning("uv sync failed: %s", uv_stderr.decode().strip())
                else:
                    logger.info("Ran uv sync for project %s", req.name)

            # Read the actual checked-out branch and store it
            branch_proc = await asyncio.create_subprocess_exec(
                "git",
                "symbolic-ref",
                "--short",
                "HEAD",
                cwd=clone_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            branch_out, _ = await branch_proc.communicate()
            if branch_proc.returncode == 0:
                project.default_branch = branch_out.decode().strip()

            logger.info(
                "Cloned %s to %s (branch: %s)",
                git_repo_url,
                clone_path,
                project.default_branch,
            )

            # Check if repo is already claimed by another project
            claim_check = check_unclaimed(clone_path)
            if claim_check.status == ManifestStatus.CLAIMED_PROD:
                shutil.rmtree(Path(clone_path).parent)
                raise HTTPException(status_code=409, detail=claim_check.reason)
            if claim_check.status == ManifestStatus.CLAIMED_OTHER:
                shutil.rmtree(Path(clone_path).parent)
                raise HTTPException(status_code=409, detail=claim_check.reason)

            # Create .team-agent/agents/ directory and write manifest
            (Path(clone_path) / ".team-agent" / "agents").mkdir(
                parents=True, exist_ok=True
            )
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
                json={
                    "project_name": req.name,
                    "name": "Zimomo",
                    "member_type": "coordinator",
                },
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
            "git",
            "fetch",
            "origin",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await fetch_proc.communicate()

        # Validate branch exists on remote
        check_proc = await asyncio.create_subprocess_exec(
            "git",
            "branch",
            "-r",
            "--list",
            f"origin/{req.default_branch}",
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
            "git",
            "checkout",
            req.default_branch,
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
            "git",
            "pull",
            "origin",
            req.default_branch,
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await pull_proc.communicate()

        project.default_branch = req.default_branch
        await session.commit()
        await session.refresh(project)

        logger.info(
            "Switched project %s to branch %s", project.name, req.default_branch
        )

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

        # Fetch latest refs and prune stale tracking branches
        fetch_proc = await asyncio.create_subprocess_exec(
            "git",
            "fetch",
            "--prune",
            "origin",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await fetch_proc.communicate()

        # List remote branches
        proc = await asyncio.create_subprocess_exec(
            "git",
            "branch",
            "-r",
            "--format=%(refname:short)",
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
            "git",
            "symbolic-ref",
            "--short",
            "HEAD",
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


@router.get("/projects/{project_id}/board")
async def get_board(project_id: uuid.UUID):
    """Fetch project board items from GitHub Projects v2."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project not found")

    manifest = read_manifest(project.clone_path)
    if not manifest or not manifest.get("board"):
        raise HTTPException(
            status_code=404,
            detail="No board configured for this project",
        )

    board = manifest["board"]
    project_number = board["project_number"]
    owner = settings.github_owner

    # Use GraphQL to get items with all field values (dates, status, etc.)
    query = (
        "query {"
        f'  user(login: "{owner}") {{'
        f"    projectV2(number: {project_number}) {{"
        "      items(first: 100) {"
        "        nodes {"
        "          id"
        "          fieldValues(first: 20) {"
        "            nodes {"
        "              ... on ProjectV2ItemFieldSingleSelectValue {"
        "                name"
        "                field { ... on ProjectV2SingleSelectField { name } }"
        "              }"
        "              ... on ProjectV2ItemFieldDateValue {"
        "                date"
        "                field { ... on ProjectV2FieldCommon { name } }"
        "              }"
        "            }"
        "          }"
        "          content {"
        "            ... on Issue {"
        "              title"
        "              number"
        "              url"
        "              body"
        "              labels(first: 10) { nodes { name } }"
        "              assignees(first: 5) { nodes { login avatarUrl } }"
        "            }"
        "          }"
        "        }"
        "      }"
        "    }"
        "  }"
        "}"
    )

    proc = await asyncio.create_subprocess_exec(
        GH_BIN,
        "api",
        "graphql",
        "-f",
        f"query={query}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch board items: {stderr.decode().strip()}",
        )

    result = json.loads(stdout.decode())
    raw_items = (
        result.get("data", {})
        .get("user", {})
        .get("projectV2", {})
        .get("items", {})
        .get("nodes", [])
    )

    items = []
    for raw in raw_items:
        content = raw.get("content")
        if not content:
            continue

        # Extract field values
        status = ""
        start_date = ""
        target_date = ""
        for fv in raw.get("fieldValues", {}).get("nodes", []):
            field_name = fv.get("field", {}).get("name", "")
            if field_name == "Status":
                status = fv.get("name", "")
            elif field_name == "Start date":
                start_date = fv.get("date", "")
            elif field_name == "Target date":
                target_date = fv.get("date", "")

        labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]
        assignees = [
            {"login": a["login"], "avatarUrl": a.get("avatarUrl", "")}
            for a in content.get("assignees", {}).get("nodes", [])
        ]

        items.append(
            {
                "id": raw["id"],
                "title": content.get("title", ""),
                "number": content.get("number"),
                "url": content.get("url", ""),
                "body": content.get("body", ""),
                "status": status,
                "startDate": start_date,
                "targetDate": target_date,
                "labels": labels,
                "assignees": assignees,
            }
        )

    return {
        "board": {
            "project_number": project_number,
            "status_options": list(board.get("status_options", {}).keys()),
        },
        "items": items,
    }
