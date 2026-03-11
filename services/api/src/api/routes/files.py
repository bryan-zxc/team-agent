import asyncio
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ..database import async_session
from ..guards import get_current_user, get_unlocked_project
from ..models.chat import Chat
from ..models.project import Project
from ..models.workload import Workload

router = APIRouter(dependencies=[Depends(get_current_user)])


async def _get_clone_path(project_id: uuid.UUID) -> Path:
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(
                status_code=404, detail="Project not found or has no cloned repo"
            )
    return Path(project.clone_path)


async def _resolve_repo_path(
    project_id: uuid.UUID, chat_id: uuid.UUID | None = None
) -> Path:
    """Return the repo root, resolving to a worktree if chat_id maps to one."""
    clone_path = await _get_clone_path(project_id)

    if chat_id is None:
        return clone_path

    async with async_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat or not chat.workload_id:
            return clone_path

        workload = await session.get(Workload, chat.workload_id)
        if not workload or not workload.worktree_branch:
            return clone_path

    slug = workload.worktree_branch.removeprefix("workload/")
    worktree_path = clone_path.parent / "worktrees" / slug

    if worktree_path.is_dir():
        return worktree_path

    return clone_path


def _validate_path(clone_path: Path, relative_path: str) -> Path:
    """Resolve and validate that the path stays within the clone directory."""
    if ".." in relative_path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    resolved = (clone_path / relative_path).resolve()
    clone_resolved = clone_path.resolve()

    if not str(resolved).startswith(str(clone_resolved)):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    return resolved


def _is_gitignored(clone_path: Path, file_path: Path) -> bool:
    """Check if a file is ignored by git using .gitignore patterns.

    Simple heuristic: skip common ignored directories. A full implementation
    would shell out to `git check-ignore` but this covers the main cases.
    """
    rel = file_path.relative_to(clone_path)
    parts = rel.parts
    ignored_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".next",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
        ".ruff_cache",
        ".pixi",
    }
    for part in parts:
        if part in ignored_dirs:
            return True
    return False


@router.get("/projects/{project_id}/files")
async def list_files(project_id: uuid.UUID, path: str = ""):
    clone_path = await _get_clone_path(project_id)
    target = _validate_path(clone_path, path)

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries = []
    try:
        for item in sorted(
            target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if item.name.startswith(".") and item.name in {".git"}:
                continue
            if _is_gitignored(clone_path, item):
                continue

            rel_path = str(item.relative_to(clone_path))
            entries.append(
                {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "path": rel_path,
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return entries


@router.get("/projects/{project_id}/files/content")
async def read_file(project_id: uuid.UUID, path: str, chat_id: uuid.UUID | None = None):
    clone_path = await _resolve_repo_path(project_id, chat_id)
    target = _validate_path(clone_path, path)

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File is not a text file")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"content": content, "path": path}


class WriteFileRequest(BaseModel):
    content: str


@router.put("/projects/{project_id}/files/content")
async def write_file(
    path: str,
    req: WriteFileRequest,
    project: Project = Depends(get_unlocked_project),
    chat_id: uuid.UUID | None = None,
):
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = await _resolve_repo_path(project.id, chat_id)
    target = _validate_path(clone_path, path)

    if not target.parent.exists():
        raise HTTPException(status_code=400, detail="Parent directory does not exist")

    try:
        target.write_text(req.content, encoding="utf-8")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"ok": True, "path": path}


class CreateFileRequest(BaseModel):
    path: str
    is_directory: bool = False


@router.post("/projects/{project_id}/files")
async def create_file(
    req: CreateFileRequest,
    project: Project = Depends(get_unlocked_project),
):
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = Path(project.clone_path)
    target = _validate_path(clone_path, req.path)

    if target.exists():
        raise HTTPException(status_code=409, detail="Path already exists")

    try:
        if req.is_directory:
            target.mkdir(parents=True, exist_ok=False)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"ok": True, "path": req.path}


@router.delete("/projects/{project_id}/files")
async def delete_file(
    path: str,
    project: Project = Depends(get_unlocked_project),
):
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = Path(project.clone_path)
    target = _validate_path(clone_path, path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    try:
        if target.is_dir():
            target.rmdir()  # Only removes empty directories
        else:
            target.unlink()
    except OSError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True}


class RenameFileRequest(BaseModel):
    old_path: str
    new_name: str


@router.patch("/projects/{project_id}/files")
async def rename_file(
    req: RenameFileRequest,
    project: Project = Depends(get_unlocked_project),
):
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = Path(project.clone_path)
    source = _validate_path(clone_path, req.old_path)

    if not source.exists():
        raise HTTPException(status_code=404, detail="Source not found")

    new_path = source.parent / req.new_name
    _validate_path(clone_path, str(new_path.relative_to(clone_path)))

    if new_path.exists():
        raise HTTPException(status_code=409, detail="Target already exists")

    try:
        source.rename(new_path)
    except OSError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "path": str(new_path.relative_to(clone_path))}


@router.get("/projects/{project_id}/raw/{file_path:path}")
async def serve_raw(
    project_id: uuid.UUID, file_path: str, chat_id: uuid.UUID | None = None
):
    """Serve a project file with its actual MIME type for iframe previews."""
    clone_path = await _resolve_repo_path(project_id, chat_id)
    target = _validate_path(clone_path, file_path)

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = target.read_bytes()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    mime_type, _ = mimetypes.guess_type(target.name)
    if mime_type is None:
        mime_type = "application/octet-stream"

    return Response(content=content, media_type=mime_type)


MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB per file
CHUNK_SIZE = 8192


@router.post("/projects/{project_id}/files/upload")
async def upload_files(
    directory: str = Form("data/raw/"),
    files: list[UploadFile] = File(...),
    project: Project = Depends(get_unlocked_project),
):
    """Upload one or more files to a directory in the project repo."""
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = Path(project.clone_path)

    dest_dir = _validate_path(clone_path, directory)
    dest_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    errors = []

    for file in files:
        filename = file.filename or "unnamed"

        # Reject unsafe filenames
        if ".." in filename or "/" in filename or "\x00" in filename:
            errors.append({"filename": filename, "detail": "Invalid filename"})
            continue

        file_path = _validate_path(clone_path, f"{directory}/{filename}")
        total_size = 0

        try:
            with open(file_path, "wb") as f:
                while chunk := await file.read(CHUNK_SIZE):
                    total_size += len(chunk)
                    if total_size > MAX_UPLOAD_SIZE:
                        break
                    f.write(chunk)

            if total_size > MAX_UPLOAD_SIZE:
                file_path.unlink(missing_ok=True)
                errors.append(
                    {"filename": filename, "detail": "File exceeds 100 MB limit"}
                )
                continue

            rel_path = str(file_path.relative_to(clone_path))
            uploaded.append({"path": rel_path, "size": total_size})
        except PermissionError:
            errors.append({"filename": filename, "detail": "Permission denied"})
        finally:
            await file.close()

    return {"uploaded": uploaded, "errors": errors}


# ── Git operations ──────────────────────────────────────────────────────────


async def _run_git(*args: str, cwd: str) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


class CommitRequest(BaseModel):
    paths: list[str]
    message: str


@router.post("/projects/{project_id}/files/commit")
async def commit_and_push(
    req: CommitRequest,
    project: Project = Depends(get_unlocked_project),
    chat_id: uuid.UUID | None = None,
):
    """Stage specified files, commit, and push."""
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")

    repo_root = await _resolve_repo_path(project.id, chat_id)
    cwd = str(repo_root)

    # Validate all paths are within the repo
    for p in req.paths:
        target = _validate_path(repo_root, p)
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {p}")

    # Stage
    rc, _, stderr = await _run_git("add", *req.paths, cwd=cwd)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"git add failed: {stderr}")

    # Commit
    rc, _, stderr = await _run_git(
        "-c",
        "user.name=team-agent",
        "-c",
        "user.email=noreply@team-agent",
        "commit",
        "-m",
        req.message,
        cwd=cwd,
    )
    if rc != 0 and "nothing to commit" not in stderr:
        raise HTTPException(status_code=500, detail=f"git commit failed: {stderr}")

    # Push
    rc, _, stderr = await _run_git("push", cwd=cwd)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"git push failed: {stderr}")

    return {"ok": True}
