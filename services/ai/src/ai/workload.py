"""Workload session management — worktree creation, SDK client lifecycle, and message relay."""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from .config import settings

logger = logging.getLogger(__name__)

_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Session registry: workload_id → {client, task, workload_data}
_sessions: dict[str, dict] = {}


def _slugify(title: str, workload_id: str) -> str:
    """Convert a workload title to a branch-safe slug with UUID suffix for uniqueness."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    slug = slug[:50]
    return f"{slug}-{workload_id[:8]}"


async def _ensure_worktree(clone_path: str, slug: str) -> Path:
    """Create or reuse a git worktree for the workload.

    Worktree: {clone_path}/../worktrees/{slug}
    Branch:   workload/{slug}
    """
    clone = Path(clone_path)
    worktree_dir = clone.parent / "worktrees"
    worktree_path = worktree_dir / slug
    branch_name = f"workload/{slug}"

    if worktree_path.exists():
        logger.info("Reusing existing worktree at %s", worktree_path)
        return worktree_path

    worktree_dir.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "add", str(worktree_path), "-b", branch_name,
        cwd=clone_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        if "already exists" in error_msg:
            proc2 = await asyncio.create_subprocess_exec(
                "git", "worktree", "add", str(worktree_path), branch_name,
                cwd=clone_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr2 = await proc2.communicate()
            if proc2.returncode != 0:
                raise RuntimeError(f"Failed to create worktree: {stderr2.decode().strip()}")
        else:
            raise RuntimeError(f"Failed to create worktree: {error_msg}")

    logger.info("Created worktree at %s (branch: %s)", worktree_path, branch_name)
    return worktree_path


def _build_system_prompt(agent_profile: str, workload_data: dict) -> dict:
    """Build a SystemPromptPreset with claude_code base + workload context appended."""
    parts = []

    if agent_profile:
        parts.append(f"## Your Identity\n\n{agent_profile}")

    parts.append(
        "## Current Workload\n\n"
        f"**Title:** {workload_data['title']}\n\n"
        f"**Description:** {workload_data['description']}"
    )

    if workload_data.get("background_context"):
        parts.append(f"**Background Context:** {workload_data['background_context']}")

    if workload_data.get("problem"):
        parts.append(f"**Problem/Challenge:** {workload_data['problem']}")

    parts.append(
        "You are working in an isolated git worktree. Make your changes, "
        "commit them when appropriate, and provide a summary when done."
    )

    return {
        "type": "preset",
        "preset": "claude_code",
        "append": "\n\n".join(parts),
    }


def _build_initial_prompt(workload_data: dict) -> str:
    """Build the first message sent to the Claude Code agent."""
    parts = [
        f"# Workload: {workload_data['title']}",
        "",
        workload_data["description"],
    ]

    if workload_data.get("background_context"):
        parts.extend(["", "## Background Context", "", workload_data["background_context"]])

    if workload_data.get("problem"):
        parts.extend(["", "## Problem", "", workload_data["problem"]])

    parts.extend(["", "Please work through this task. Commit your changes when appropriate."])
    return "\n".join(parts)


async def _get_coordinator_for_chat(chat_id: str) -> dict:
    """Look up the coordinator member for the project owning a chat."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT pm.id, pm.display_name "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN project_members pm ON pm.project_id = r.project_id "
            "WHERE c.id = $1 AND pm.type = 'coordinator'",
            uuid.UUID(chat_id),
        )
        if not row:
            raise ValueError(f"No coordinator found for chat {chat_id}")
        return {"id": str(row["id"]), "display_name": row["display_name"]}
    finally:
        await conn.close()


async def _relay_messages(
    workload_id: str,
    client: ClaudeSDKClient,
    workload_data: dict,
    redis_client: aioredis.Redis,
) -> None:
    """Relay messages from ClaudeSDKClient to Redis chat:responses.

    Runs as a background task for the lifetime of the workload session.
    """
    chat_id = workload_data["chat_id"]
    member_id = workload_data["member_id"]
    display_name = workload_data["display_name"]
    main_chat_id = workload_data["main_chat_id"]

    try:
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                text_parts = [
                    block.text for block in msg.content if isinstance(block, TextBlock)
                ]
                if not text_parts:
                    continue

                text = "\n".join(text_parts)
                structured_content = json.dumps({
                    "blocks": [{"type": "text", "value": text}],
                    "mentions": [],
                })

                response = {
                    "id": str(uuid.uuid4()),
                    "chat_id": chat_id,
                    "member_id": member_id,
                    "display_name": display_name,
                    "type": "ai",
                    "content": structured_content,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await redis_client.publish("chat:responses", json.dumps(response))

            elif isinstance(msg, ResultMessage):
                logger.info(
                    "Workload %s completed (session: %s, error: %s, turns: %d)",
                    workload_id[:8], msg.session_id, msg.is_error, msg.num_turns,
                )

                # Store session_id and update status
                conn = await asyncpg.connect(_dsn)
                try:
                    await conn.execute(
                        "UPDATE workloads SET status = 'needs_attention', session_id = $1, "
                        "updated_at = $2 WHERE id = $3",
                        msg.session_id, datetime.now(timezone.utc), uuid.UUID(workload_id),
                    )
                finally:
                    await conn.close()

                # Publish summary to main chat
                summary = f"Workload **{workload_data['title']}** has finished and needs attention."
                if msg.result:
                    summary += f"\n\nSummary: {msg.result}"

                coordinator = await _get_coordinator_for_chat(main_chat_id)
                structured_summary = json.dumps({
                    "blocks": [{"type": "text", "value": summary}],
                    "mentions": [],
                })

                main_response = {
                    "id": str(uuid.uuid4()),
                    "chat_id": main_chat_id,
                    "member_id": coordinator["id"],
                    "display_name": coordinator["display_name"],
                    "type": "coordinator",
                    "content": structured_summary,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await redis_client.publish("chat:responses", json.dumps(main_response))

                _sessions.pop(workload_id, None)
                return

    except asyncio.CancelledError:
        logger.info("Relay task cancelled for workload %s", workload_id[:8])
        _sessions.pop(workload_id, None)
    except Exception:
        logger.exception("Relay task error for workload %s", workload_id[:8])
        try:
            conn = await asyncpg.connect(_dsn)
            try:
                await conn.execute(
                    "UPDATE workloads SET status = 'error', updated_at = $1 WHERE id = $2",
                    datetime.now(timezone.utc), uuid.UUID(workload_id),
                )
            finally:
                await conn.close()
        except Exception:
            logger.exception("Failed to update workload status to error")
        _sessions.pop(workload_id, None)


async def start_workload_session(
    workload_data: dict,
    clone_path: str,
    redis_client: aioredis.Redis,
) -> None:
    """Start a Claude Code agent session for a workload.

    Creates (or reuses) a git worktree, starts a ClaudeSDKClient,
    and launches the relay task as a background asyncio task.
    """
    workload_id = workload_data["id"]

    if workload_id in _sessions:
        logger.warning("Session already active for workload %s, skipping", workload_id[:8])
        return

    slug = _slugify(workload_data["title"], workload_id)

    # 1. Create/reuse worktree
    try:
        worktree_path = await _ensure_worktree(clone_path, slug)
    except RuntimeError:
        logger.exception("Failed to create worktree for workload %s", workload_id[:8])
        conn = await asyncpg.connect(_dsn)
        try:
            await conn.execute(
                "UPDATE workloads SET status = 'error', updated_at = $1 WHERE id = $2",
                datetime.now(timezone.utc), uuid.UUID(workload_id),
            )
        finally:
            await conn.close()
        return

    # 2. Update worktree_branch and status in DB
    branch_name = f"workload/{slug}"
    conn = await asyncpg.connect(_dsn)
    try:
        await conn.execute(
            "UPDATE workloads SET worktree_branch = $1, status = 'running', "
            "updated_at = $2 WHERE id = $3",
            branch_name, datetime.now(timezone.utc), uuid.UUID(workload_id),
        )
    finally:
        await conn.close()

    # 3. Load agent profile for system prompt
    profile_path = Path(clone_path) / ".agent" / f"{workload_data['display_name'].lower()}.md"
    agent_profile = profile_path.read_text() if profile_path.exists() else ""

    # 4. Build SDK options
    is_resume = bool(workload_data.get("session_id"))

    options = ClaudeAgentOptions(
        cwd=str(worktree_path),
        resume=workload_data.get("session_id") if is_resume else None,
        system_prompt=_build_system_prompt(agent_profile, workload_data),
        permission_mode="acceptEdits",
    )

    # 5. Connect
    try:
        client = ClaudeSDKClient(options)
        await client.connect()
    except Exception:
        logger.exception("Failed to connect ClaudeSDKClient for workload %s", workload_id[:8])
        conn = await asyncpg.connect(_dsn)
        try:
            await conn.execute(
                "UPDATE workloads SET status = 'error', updated_at = $1 WHERE id = $2",
                datetime.now(timezone.utc), uuid.UUID(workload_id),
            )
        finally:
            await conn.close()
        return

    # 6. Register and start relay
    _sessions[workload_id] = {
        "client": client,
        "task": None,
        "workload_data": workload_data,
    }

    relay_task = asyncio.create_task(
        _relay_messages(workload_id, client, workload_data, redis_client),
        name=f"workload-relay-{workload_id[:8]}",
    )
    _sessions[workload_id]["task"] = relay_task

    # 7. Send initial prompt (or skip if resuming)
    if not is_resume:
        initial_prompt = _build_initial_prompt(workload_data)
        await client.query(initial_prompt)
        logger.info("Sent initial prompt to workload %s", workload_id[:8])
    else:
        logger.info(
            "Resumed session %s for workload %s",
            workload_data["session_id"], workload_id[:8],
        )


async def route_message(workload_id: str, prompt: str) -> bool:
    """Route a follow-up message to an active workload session.

    Returns True if delivered, False if no active session.
    """
    session = _sessions.get(workload_id)
    if not session:
        logger.warning("No active session for workload %s", workload_id[:8])
        return False

    client = session["client"]
    await client.query(prompt)
    logger.info("Routed follow-up message to workload %s", workload_id[:8])
    return True


async def shutdown_all_sessions() -> None:
    """Gracefully disconnect all active workload sessions."""
    for workload_id, session in list(_sessions.items()):
        logger.info("Shutting down session for workload %s", workload_id[:8])
        task = session.get("task")
        if task and not task.done():
            task.cancel()
        client = session.get("client")
        if client:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Error disconnecting workload %s", workload_id[:8])
    _sessions.clear()
