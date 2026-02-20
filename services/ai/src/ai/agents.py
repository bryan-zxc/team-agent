"""Agent profile generation."""

import logging
import uuid
from pathlib import Path

import asyncpg

from .config import settings
from .llm import llm, AgentProfile

logger = logging.getLogger(__name__)

# asyncpg uses postgresql:// not postgresql+asyncpg://
_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _agents_dir(project_name: str) -> Path:
    return Path(settings.agents_dir) / project_name


def _profile_path(project_name: str, agent_name: str) -> Path:
    return _agents_dir(project_name) / f"{agent_name.lower()}.md"


async def _get_existing_agent_names(project_name: str) -> list[str]:
    """Load existing AI agent names for a project from the database."""
    conn = await asyncpg.connect(_dsn)
    try:
        rows = await conn.fetch(
            "SELECT pm.display_name FROM project_members pm "
            "JOIN projects p ON p.id = pm.project_id "
            "WHERE pm.type = 'ai' AND p.name = $1",
            project_name,
        )
        return [r["display_name"] for r in rows]
    finally:
        await conn.close()


async def _insert_project_member(project_name: str, agent_name: str) -> None:
    """Insert a new AI project member into the database."""
    conn = await asyncpg.connect(_dsn)
    try:
        project_id = await conn.fetchval(
            "SELECT id FROM projects WHERE name = $1", project_name
        )
        if not project_id:
            raise RuntimeError(f"Project '{project_name}' not found in database")

        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, NULL, $3, 'ai', NOW())",
            uuid.uuid4(),
            project_id,
            agent_name,
        )
    finally:
        await conn.close()


async def generate_agent_profile(
    project_name: str,
    name: str | None = None,
) -> str:
    """Generate an agent profile markdown file using the LLM.

    If name is not provided, the LLM picks a Pop Mart character name.
    Creates a project_member record and writes the profile to
    agents/{project_name}/{name}.md. Returns the file path.
    """
    existing_names = await _get_existing_agent_names(project_name)

    prompt = f"Generate a personality profile for an AI team member{' named ' + name if name else ''}."
    if existing_names:
        prompt += f" These names are already taken: {', '.join(existing_names)}. Pick a different name."

    messages = [{"role": "user", "content": prompt}]

    result = await llm.a_get_response(
        messages=messages,
        response_format=AgentProfile,
    )

    if not isinstance(result, AgentProfile):
        raise RuntimeError(f"Expected AgentProfile, got {type(result)}")

    # Insert into database as AI project member
    await _insert_project_member(project_name, result.name)

    # Write markdown file
    profile_dir = _agents_dir(project_name)
    profile_dir.mkdir(parents=True, exist_ok=True)

    md_content = f"""# {result.name}

## Pronoun
{result.pronoun}

## Personality
{result.personality}

## Specialisation
{result.specialisation}

## Work Done
"""

    file_path = _profile_path(project_name, result.name)
    file_path.write_text(md_content)

    logger.info("Generated agent profile: %s", file_path)
    return str(file_path)
