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
    """Extract YAML frontmatter fields using regex (no pyyaml dependency).

    Handles single-line values and YAML folded scalars (> or |) where the
    value continues on indented lines below the key.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    body = match.group(1)
    lines = body.split("\n")
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_parts: list[str] = []

    for line in lines:
        field_match = _FIELD_RE.match(line)
        if field_match:
            # Flush previous key
            if current_key is not None:
                fields[current_key] = " ".join(current_parts).strip().strip("\"'")
            current_key = field_match.group(1)
            value = field_match.group(2).strip().strip("\"'")
            # If value is a YAML block scalar indicator, start collecting lines
            if value in (">", "|", ">-", "|-"):
                current_parts = []
            else:
                current_parts = [value]
        elif current_key is not None and line.startswith("  "):
            # Indented continuation line
            current_parts.append(line.strip())

    # Flush last key
    if current_key is not None:
        fields[current_key] = " ".join(current_parts).strip().strip("\"'")

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
