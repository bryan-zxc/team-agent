"""Admin session management — Claude Code sessions on the project clone directory."""

import asyncio
import logging
import os
import uuid
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import settings
from .session import (
    _sessions,
    publish_status_event,
    register_session,
    relay_messages,
    stop_session,
    unregister_session,
    update_chat_status,
)
from .tool_approval import make_can_use_tool

logger = logging.getLogger(__name__)

_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def fetch_admin_chat_data(chat_id: str) -> dict | None:
    """Fetch admin chat data from DB for session start/resume.

    Returns a dict with chat_id, session_id, status, room_id, project_id,
    clone_path, permission_mode, member_id (coordinator), display_name.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT c.id AS chat_id, c.room_id, c.status, c.session_id, "
            "c.permission_mode, "
            "p.id AS project_id, p.clone_path, "
            "pm.id AS member_id, pm.display_name "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN projects p ON p.id = r.project_id "
            "JOIN project_members pm ON pm.project_id = p.id AND pm.type = 'coordinator' "
            "WHERE c.id = $1 AND c.type = 'admin'",
            uuid.UUID(chat_id),
        )
        if not row:
            return None

        return {
            "chat_id": str(row["chat_id"]),
            "room_id": str(row["room_id"]),
            "status": row["status"],
            "session_id": row["session_id"],
            "permission_mode": row["permission_mode"] or "default",
            "project_id": str(row["project_id"]),
            "clone_path": row["clone_path"],
            "member_id": str(row["member_id"]),
            "display_name": row["display_name"],
        }
    finally:
        await conn.close()


async def _stop_other_admin_sessions(
    project_id: str, exclude_chat_id: str, redis_client: aioredis.Redis,
) -> None:
    """Stop any other active admin session for the same project."""
    for session_key, session in list(_sessions.items()):
        if session.get("session_type") != "admin":
            continue
        if session.get("project_id") == project_id and session_key != exclude_chat_id:
            logger.info("Stopping previous admin session %s for project %s", session_key[:8], project_id[:8])
            await stop_session(session_key, "completed", redis_client)


async def start_admin_session(
    chat_data: dict,
    redis_client: aioredis.Redis,
) -> None:
    """Start a Claude Code agent session for an admin chat.

    Runs on the project's clone directory (no worktree).
    """
    chat_id = chat_data["chat_id"]
    clone_path = chat_data["clone_path"]
    room_id = chat_data.get("room_id", "")
    project_id = chat_data.get("project_id", "")

    if chat_id in _sessions:
        logger.warning("Session already active for admin chat %s, skipping", chat_id[:8])
        return

    # One active admin session per project
    await _stop_other_admin_sessions(project_id, chat_id, redis_client)

    await update_chat_status(chat_id, "running")
    await publish_status_event(redis_client, chat_id, "running", room_id, chat_type="admin")

    # Pre-register session
    is_resume = bool(chat_data.get("session_id"))

    register_session(chat_id, {
        "session_type": "admin",
        "client": None,
        "task": None,
        "chat_id": chat_id,
        "member_id": chat_data["member_id"],
        "display_name": chat_data["display_name"],
        "room_id": room_id,
        "clone_path": clone_path,
        "project_id": project_id,
        "session_approvals": set(),
        "pending_approvals": {},
    })

    can_use_tool = make_can_use_tool(
        session_key=chat_id,
        clone_path=clone_path,
        working_dir=clone_path,
        session_state=_sessions[chat_id],
        redis_client=redis_client,
        chat_id=chat_id,
        member_id=chat_data["member_id"],
        display_name=chat_data["display_name"],
    )

    # Load coordinator profile for system prompt
    coordinator_name = chat_data["display_name"]
    profile_path = Path(clone_path) / ".team-agent" / "agents" / f"{coordinator_name.lower()}.md"
    agent_profile = profile_path.read_text() if profile_path.exists() else ""

    system_prompt = {"type": "preset", "preset": "claude_code"}
    if agent_profile:
        system_prompt["append"] = f"## Your Identity\n\n{agent_profile}"

    # Build environment
    cli_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    cli_env["PLAYWRIGHT_MCP_SANDBOX"] = "false"

    # Git identity — attribute commits to coordinator
    cli_env["GIT_AUTHOR_NAME"] = coordinator_name
    cli_env["GIT_COMMITTER_NAME"] = coordinator_name
    cli_env["GIT_AUTHOR_EMAIL"] = f"{coordinator_name.lower()}@team-agent"
    cli_env["GIT_COMMITTER_EMAIL"] = f"{coordinator_name.lower()}@team-agent"

    permission_mode = chat_data.get("permission_mode", "default")

    options = ClaudeAgentOptions(
        cwd=clone_path,
        resume=chat_data.get("session_id") if is_resume else None,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        can_use_tool=can_use_tool,
        setting_sources=["project", "user"],
        env=cli_env,
        include_partial_messages=True,
    )

    # Connect
    try:
        client = ClaudeSDKClient(options)
        await client.connect()
    except Exception:
        logger.exception("Failed to connect ClaudeSDKClient for admin chat %s", chat_id[:8])
        unregister_session(chat_id)
        await update_chat_status(chat_id, "needs_attention")
        await publish_status_event(redis_client, chat_id, "needs_attention", room_id, chat_type="admin")
        return

    # Finish registration and start relay
    _sessions[chat_id]["client"] = client

    relay_task = asyncio.create_task(
        relay_messages(chat_id, client, redis_client, completion_status="completed"),
        name=f"admin-relay-{chat_id[:8]}",
    )
    _sessions[chat_id]["task"] = relay_task

    if is_resume:
        logger.info("Resumed admin session %s for chat %s", chat_data["session_id"], chat_id[:8])
    else:
        logger.info("Started admin session for chat %s", chat_id[:8])


async def shutdown_all_admin_sessions(redis_client: aioredis.Redis) -> None:
    """Gracefully stop all active admin sessions."""
    for session_key, session in list(_sessions.items()):
        if session.get("session_type") != "admin":
            continue
        logger.info("Shutting down admin session %s", session_key[:8])
        await stop_session(session_key, "completed", redis_client)
