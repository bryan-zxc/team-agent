import re
import uuid
from pathlib import Path

from sqlalchemy import func, select

from .database import async_session
from .models.project import Project
from .models.project_member import ProjectMember

# Patterns matched inside text blocks (order matters for priority)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")  # [label](url)
_MENTION_RE = re.compile(r"@(\S+)")  # @name
_SKILL_RE = re.compile(r"(?<!\S)/([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?!\S)")  # /skill-name

# Combined pattern: match any of the three, leftmost wins
_COMBINED_RE = re.compile(
    r"(?P<link>\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\))"
    r"|(?P<mention>@(?P<mname>\S+))"
    r"|(?P<skill>(?<!\S)/(?P<sname>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?!\S))"
)


async def _get_member_map(
    project_id: uuid.UUID,
) -> dict[str, ProjectMember]:
    """Return {lowercase_display_name: member} for all project members."""
    async with async_session() as session:
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
        result = await session.execute(stmt)
        members = result.scalars().all()
    return {m.display_name.lower(): m for m in members}


def _get_skill_names(clone_path: Path) -> set[str]:
    """Return set of skill names from .claude/skills/ directories."""
    skills_dir = clone_path / ".claude" / "skills"
    if not skills_dir.is_dir():
        return set()
    names = set()
    for d in skills_dir.iterdir():
        if d.is_dir() and (d / "SKILL.md").is_file():
            names.add(d.name)
    return names


async def _get_clone_path(project_id: uuid.UUID) -> Path | None:
    """Get the clone path for a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project and project.clone_path:
            return Path(project.clone_path)
    return None


def _split_text_block(
    value: str,
    member_map: dict[str, ProjectMember],
    skill_names: set[str],
) -> tuple[list[dict], list[str]]:
    """Split a text value into typed blocks. Returns (blocks, new_mention_ids)."""
    blocks: list[dict] = []
    new_mentions: list[str] = []
    last_end = 0

    for m in _COMBINED_RE.finditer(value):
        if m.group("link"):
            new_block = {
                "type": "link",
                "url": m.group("url"),
                "label": m.group("label"),
            }
        elif m.group("mention"):
            name = m.group("mname")
            member = member_map.get(name.lower())
            if not member:
                continue  # Unknown mention — leave as plain text
            new_block = {
                "type": "mention",
                "member_id": str(member.id),
                "display_name": member.display_name,
            }
            new_mentions.append(str(member.id))
        elif m.group("skill"):
            name = m.group("sname")
            if name not in skill_names:
                continue  # Unknown skill — leave as plain text
            new_block = {"type": "skill", "name": name}
        else:
            continue

        # Only emit preceding text once we know the match is valid
        if m.start() > last_end:
            blocks.append({"type": "text", "value": value[last_end : m.start()]})
        blocks.append(new_block)
        last_end = m.end()

    # Trailing text
    if last_end < len(value):
        blocks.append({"type": "text", "value": value[last_end:]})

    return blocks, new_mentions


async def convert_text_blocks(
    blocks: list[dict],
    project_id: uuid.UUID,
    mentions: list[str],
) -> tuple[list[dict], list[str]]:
    """Scan text blocks for @mentions, /skills, and [links] and split into typed blocks.

    Returns (converted_blocks, updated_mentions).
    Non-text blocks pass through unchanged.
    """
    # Check if there are any text blocks worth scanning
    has_text = any(b.get("type") == "text" for b in blocks)
    if not has_text:
        return blocks, mentions

    member_map = await _get_member_map(project_id)
    clone_path = await _get_clone_path(project_id)
    skill_names = _get_skill_names(clone_path) if clone_path else set()

    result_blocks: list[dict] = []
    new_mentions = list(mentions)  # Copy to avoid mutating caller's list

    for block in blocks:
        if block.get("type") != "text":
            result_blocks.append(block)
            continue

        value = block.get("value", "")
        if not value:
            result_blocks.append(block)
            continue

        split_blocks, added_mentions = _split_text_block(
            value, member_map, skill_names
        )
        result_blocks.extend(split_blocks)

        for mid in added_mentions:
            if mid not in new_mentions:
                new_mentions.append(mid)

    return result_blocks, new_mentions
