import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..database import async_session
from ..guards import get_unlocked_project
from ..models.project import Project

router = APIRouter()


async def _get_clone_path(project_id: uuid.UUID) -> Path:
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project not found or has no cloned repo")
    return Path(project.clone_path)


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
        "node_modules", ".git", "__pycache__", ".next", ".venv",
        "venv", "env", ".tox", ".pytest_cache", ".mypy_cache",
        "dist", "build", ".eggs", ".ruff_cache", ".pixi",
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
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name.startswith(".") and item.name in {".git"}:
                continue
            if _is_gitignored(clone_path, item):
                continue

            rel_path = str(item.relative_to(clone_path))
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "path": rel_path,
                "size": item.stat().st_size if item.is_file() else None,
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return entries


@router.get("/projects/{project_id}/files/content")
async def read_file(project_id: uuid.UUID, path: str):
    clone_path = await _get_clone_path(project_id)
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
):
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")
    clone_path = Path(project.clone_path)
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
