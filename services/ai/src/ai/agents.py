"""Agent profile generation."""

import asyncio
import logging
import uuid
from pathlib import Path

import asyncpg

from .config import settings
from .llm import llm, AgentProfile

logger = logging.getLogger(__name__)

# asyncpg uses postgresql:// not postgresql+asyncpg://
_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _get_clone_path(project_name: str) -> Path:
    """Resolve the clone_path for a project from the database."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchval(
            "SELECT clone_path FROM projects WHERE name = $1", project_name
        )
        if not row:
            raise RuntimeError(f"Project '{project_name}' not found or has no clone_path")
        return Path(row)
    finally:
        await conn.close()


def _agent_dir(clone_path: Path) -> Path:
    return clone_path / ".team-agent" / "agents"


def _profile_path(clone_path: Path, agent_name: str) -> Path:
    return _agent_dir(clone_path) / f"{agent_name.lower()}.md"


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


async def _insert_project_member(
    project_name: str, agent_name: str, member_type: str = "ai",
) -> uuid.UUID:
    """Insert a new project member into the database. Returns the member id."""
    conn = await asyncpg.connect(_dsn)
    try:
        project_id = await conn.fetchval(
            "SELECT id FROM projects WHERE name = $1", project_name
        )
        if not project_id:
            raise RuntimeError(f"Project '{project_name}' not found in database")

        member_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, NULL, $3, $4, NOW())",
            member_id,
            project_id,
            agent_name,
            member_type,
        )
        return member_id
    finally:
        await conn.close()


async def generate_agent_profile(
    project_name: str,
    name: str | None = None,
    member_type: str = "ai",
) -> dict:
    """Generate an agent profile markdown file using the LLM.

    If name is not provided, the LLM picks a Pop Mart character name.
    Creates a project_member record and writes the profile to
    {clone_path}/.team-agent/agents/{name}.md.

    Returns {"id": str, "display_name": str, "file_path": str}.
    """
    existing_names = await _get_existing_agent_names(project_name)

    prompt = f"Generate a personality profile for an AI team member{' named ' + name if name else ''}."
    if existing_names:
        prompt += f" These names are already taken: {', '.join(existing_names)}. Pick a different name."

    messages = [{"role": "user", "content": prompt}]

    lore_path = Path(__file__).parent / "references" / "pop-mart-characters.md"
    lore = lore_path.read_text()
    system_instruction = (
        "The following Pop Mart character descriptions are provided as inspiration. "
        "Use them as a loose guide for the agent's name and personality flavour — "
        "you do not need to follow them exactly.\n\n"
        f"{lore}"
    )

    result = await llm.a_get_response(
        messages=messages,
        response_format=AgentProfile,
        system_instruction=system_instruction,
    )

    if not isinstance(result, AgentProfile):
        raise RuntimeError(f"Expected AgentProfile, got {type(result)}")

    # Insert into database as project member
    member_id = await _insert_project_member(project_name, result.name, member_type)

    # Write markdown file into the project's cloned repo
    clone_path = await _get_clone_path(project_name)
    profile_dir = _agent_dir(clone_path)
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

    file_path = _profile_path(clone_path, result.name)
    file_path.write_text(md_content)

    # Commit and push the profile (and manifest if present) to the remote
    await _git_commit_and_push(
        clone_path, f"Add agent profile: {result.name}",
    )

    logger.info("Generated agent profile: %s", file_path)
    return {
        "id": str(member_id),
        "display_name": result.name,
        "file_path": str(file_path),
    }


async def _run_git(*args: str, cwd: Path) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


async def _git_commit_and_push(clone_path: Path, message: str) -> None:
    """Stage .team-agent/, commit, and push. Logs warnings on failure."""
    rc, _, err = await _run_git("add", ".team-agent/", cwd=clone_path)
    if rc != 0:
        logger.warning("git add failed: %s", err)
        return

    rc, _, err = await _run_git(
        "-c", "user.name=team-agent",
        "-c", "user.email=noreply@team-agent",
        "commit", "-m", message,
        cwd=clone_path,
    )
    if rc != 0:
        logger.warning("git commit failed: %s", err)
        return

    logger.info("Committed: %s", message)

    rc, _, err = await _run_git("push", cwd=clone_path)
    if rc != 0:
        logger.warning("git push failed (non-blocking): %s", err)
    else:
        logger.info("Pushed to remote")
