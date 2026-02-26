import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from ..guards import get_current_user, get_unlocked_project
from ..models.project import Project

router = APIRouter(dependencies=[Depends(get_current_user)])

# Match YAML frontmatter between --- delimiters
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w+):\s*(.+)", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter fields using regex (no pyyaml dependency)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    body = match.group(1)
    fields = {}
    for field_match in _FIELD_RE.finditer(body):
        key = field_match.group(1)
        value = field_match.group(2).strip().strip("\"'")
        fields[key] = value
    return fields


def _scan_skills(clone_path: Path) -> list[dict]:
    """Scan .claude/skills/ for valid SKILL.md files and return metadata."""
    skills_dir = clone_path / ".claude" / "skills"
    if not skills_dir.is_dir():
        return []

    results = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fields = _parse_frontmatter(text)
        name = fields.get("name")
        description = fields.get("description")
        if not name or not description:
            continue

        rel_path = str(skill_dir.relative_to(clone_path))
        results.append({
            "name": name,
            "description": description,
            "path": rel_path,
        })

    return results


@router.get("/projects/{project_id}/skills")
async def list_skills(project: Project = Depends(get_unlocked_project)):
    clone_path = Path(project.clone_path) if project.clone_path else None
    if not clone_path or not clone_path.is_dir():
        return []
    return _scan_skills(clone_path)
