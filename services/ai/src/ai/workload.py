"""Workload session management — worktree creation, SDK client lifecycle."""

import asyncio
import logging
import os
import re
import uuid
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
)

from .config import settings
from .escalation import escalate_to_admin
from .session import (
    _sessions,
    cleanup_worktree,
    publish_status_event,
    register_session,
    relay_messages,
    run_git,
    stop_session,
    unregister_session,
    update_chat_status,
)
from .tool_approval import make_can_use_tool

logger = logging.getLogger(__name__)

_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _fetch_workload_row(chat_id: str) -> dict | None:
    """Fetch the raw workload+chat+project row from DB by chat_id."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT w.id, w.title, w.description, w.permission_mode, "
            "w.member_id, w.main_chat_id, "
            "c.id AS chat_id, c.room_id, c.status, c.session_id, "
            "pm.display_name, "
            "p.clone_path, p.id AS project_id "
            "FROM chats c "
            "JOIN workloads w ON c.workload_id = w.id "
            "JOIN project_members pm ON pm.id = w.member_id "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN projects p ON p.id = r.project_id "
            "WHERE c.id = $1 AND c.type = 'workload'",
            uuid.UUID(chat_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


def _row_to_workload_data(row: dict) -> dict:
    """Convert a raw DB row into the workload_data dict for start_workload_session()."""
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "session_id": row["session_id"],
        "chat_id": str(row["chat_id"]),
        "member_id": str(row["member_id"]),
        "display_name": row["display_name"],
        "room_id": str(row["room_id"]),
        "main_chat_id": str(row["main_chat_id"]),
        "clone_path": row["clone_path"],
        "project_id": str(row["project_id"]),
        "permission_mode": row["permission_mode"],
        "background_context": None,
        "problem": None,
    }


async def fetch_workload_data_for_resume(chat_id: str) -> dict | None:
    """Fetch full workload data from DB for session resume.

    Looks up by chat_id (the universal session key). Returns the workload_data
    dict compatible with start_workload_session(), or None if not found or no session_id.
    """
    row = await _fetch_workload_row(chat_id)
    if not row or not row["session_id"]:
        return None
    return _row_to_workload_data(row)


async def fetch_workload_data_for_retry(chat_id: str) -> dict | None:
    """Fetch workload data for a fresh retry (no session_id required)."""
    row = await _fetch_workload_row(chat_id)
    if not row:
        return None
    data = _row_to_workload_data(row)
    data["session_id"] = None  # Fresh start, no resume
    return data


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
        "git",
        "worktree",
        "add",
        str(worktree_path),
        "-b",
        branch_name,
        cwd=clone_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        if "already exists" in error_msg:
            proc2 = await asyncio.create_subprocess_exec(
                "git",
                "worktree",
                "add",
                str(worktree_path),
                branch_name,
                cwd=clone_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr2 = await proc2.communicate()
            if proc2.returncode != 0:
                raise RuntimeError(
                    f"Failed to create worktree: {stderr2.decode().strip()}"
                )
        else:
            raise RuntimeError(f"Failed to create worktree: {error_msg}")

    logger.info("Created worktree at %s (branch: %s)", worktree_path, branch_name)

    # Set up Python environment if pyproject.toml exists
    if (worktree_path / "pyproject.toml").exists():
        uv_proc = await asyncio.create_subprocess_exec(
            "uv",
            "sync",
            cwd=str(worktree_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, uv_stderr = await uv_proc.communicate()
        if uv_proc.returncode != 0:
            logger.warning("uv sync failed in worktree: %s", uv_stderr.decode().strip())
        else:
            logger.info("Ran uv sync in worktree %s", worktree_path)

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
        parts.extend(
            ["", "## Background Context", "", workload_data["background_context"]]
        )

    if workload_data.get("problem"):
        parts.extend(["", "## Problem", "", workload_data["problem"]])

    parts.extend(
        ["", "Please work through this task. Commit your changes when appropriate."]
    )
    return "\n".join(parts)


def _make_stop_hook(
    workload_id: str,
    clone_path: str,
    worktree_path: Path,
    branch_name: str,
    display_name: str,
    target_branch: str,
    *,
    redis_client,
    chat_id: str,
    main_chat_id: str,
    room_id: str,
    project_id: str,
    workload_title: str,
) -> tuple:
    """Create a Stop hook that merges the workload branch into the project's default branch.

    Returns (hook_callback, merge_state_dict).
    The merge_state dict is shared with the relay handler to report merge outcome.

    On merge conflict or push failure, escalates to the admin room instead of
    retrying or silently logging.
    """
    merge_state: dict = {"succeeded": None, "target_branch": target_branch}

    async def stop_hook(
        _input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> HookJSONOutput:
        # If worktree is already gone, nothing to merge — let agent stop
        if not worktree_path.exists():
            logger.info(
                "Workload %s: worktree already removed, skipping merge", workload_id[:8]
            )
            merge_state["succeeded"] = True
            return {"continue_": False}

        # Auto-commit any uncommitted changes in the worktree
        await run_git("add", "-A", cwd=str(worktree_path))
        status_rc, status_out, _ = await run_git(
            "status", "--porcelain", cwd=str(worktree_path)
        )
        if status_rc == 0 and status_out.strip():
            commit_rc, _, commit_err = await run_git(
                "-c",
                f"user.name={display_name}",
                "-c",
                f"user.email={display_name.lower()}@team-agent",
                "commit",
                "-m",
                f"Workload {workload_id[:8]}: auto-commit changes",
                cwd=str(worktree_path),
            )
            if commit_rc == 0:
                logger.info(
                    "Workload %s: auto-committed uncommitted changes", workload_id[:8]
                )
            else:
                logger.warning(
                    "Workload %s: auto-commit failed: %s", workload_id[:8], commit_err
                )

        # Attempt merge into main
        rc, stdout, stderr = await run_git(
            "merge",
            branch_name,
            "--no-edit",
            cwd=clone_path,
        )

        if rc == 0:
            logger.info("Workload %s: merge succeeded", workload_id[:8])

            # Clean up worktree and branch
            await cleanup_worktree(clone_path, branch_name)

            # Push merged changes to remote
            push_rc, _, push_err = await run_git("push", cwd=clone_path)
            if push_rc != 0:
                # Push failure — escalate to admin room
                logger.warning(
                    "Workload %s: push failed, escalating: %s",
                    workload_id[:8],
                    push_err,
                )
                merge_state["succeeded"] = False
                admin_id = await escalate_to_admin(
                    redis_client,
                    project_id,
                    clone_path,
                    workload_chat_id=chat_id,
                    workload_title=workload_title,
                    main_chat_id=main_chat_id,
                    room_id=room_id,
                    error_type="push_failure",
                    error_details=push_err,
                    extra_context={
                        "clone_path": clone_path,
                        "target_branch": target_branch,
                    },
                )
                if admin_id:
                    merge_state["admin_chat_id"] = admin_id
                return {"continue_": False}

            logger.info("Workload %s: pushed merged changes to remote", workload_id[:8])
            merge_state["succeeded"] = True
            return {"continue_": False}

        # Merge conflict — abort and escalate to admin room
        logger.warning(
            "Workload %s: merge conflict, escalating: %s", workload_id[:8], stderr
        )
        await run_git("merge", "--abort", cwd=clone_path)
        merge_state["succeeded"] = False

        admin_id = await escalate_to_admin(
            redis_client,
            project_id,
            clone_path,
            workload_chat_id=chat_id,
            workload_title=workload_title,
            main_chat_id=main_chat_id,
            room_id=room_id,
            error_type="merge_conflict",
            error_details=stderr,
            extra_context={
                "worktree_path": str(worktree_path),
                "branch_name": branch_name,
                "target_branch": target_branch,
                "clone_path": clone_path,
            },
        )
        if admin_id:
            merge_state["admin_chat_id"] = admin_id
        return {"continue_": False}

    return stop_hook, merge_state


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
    chat_id = workload_data["chat_id"]
    room_id = workload_data.get("room_id", "")

    if chat_id in _sessions:
        logger.warning(
            "Session already active for workload %s (chat %s), skipping",
            workload_id[:8],
            chat_id[:8],
        )
        return

    slug = _slugify(workload_data["title"], workload_id)

    # 1. Create/reuse worktree
    try:
        worktree_path = await _ensure_worktree(clone_path, slug)
    except RuntimeError as exc:
        logger.exception("Failed to create worktree for workload %s", workload_id[:8])
        branch_name = f"workload/{slug}"
        await escalate_to_admin(
            redis_client,
            project_id=workload_data.get("project_id", ""),
            clone_path=clone_path,
            workload_chat_id=chat_id,
            workload_title=workload_data.get("title", "Workload"),
            main_chat_id=workload_data.get("main_chat_id", ""),
            room_id=room_id,
            error_type="worktree_failure",
            error_details=str(exc),
            extra_context={"branch_name": branch_name},
        )
        return

    # 2. Update worktree_branch and status in DB
    branch_name = f"workload/{slug}"
    conn = await asyncpg.connect(_dsn)
    try:
        await conn.execute(
            "UPDATE workloads SET worktree_branch = $1 WHERE id = $2",
            branch_name,
            uuid.UUID(workload_id),
        )
    finally:
        await conn.close()

    await update_chat_status(chat_id, "running")
    await publish_status_event(
        redis_client, chat_id, "running", room_id, chat_type="workload"
    )

    # 3. Load agent profile for system prompt
    profile_path = (
        Path(clone_path)
        / ".team-agent"
        / "agents"
        / f"{workload_data['display_name'].lower()}.md"
    )
    agent_profile = profile_path.read_text() if profile_path.exists() else ""

    # 4. Read target branch from clone (whatever is checked out)
    _, target_branch_out, _ = await run_git(
        "symbolic-ref",
        "--short",
        "HEAD",
        cwd=clone_path,
    )
    target_branch = target_branch_out.strip() if target_branch_out.strip() else "main"

    # 5. Create Stop hook for auto-merge
    stop_hook, merge_state = _make_stop_hook(
        workload_id=workload_id,
        clone_path=clone_path,
        worktree_path=worktree_path,
        branch_name=branch_name,
        display_name=workload_data["display_name"],
        target_branch=target_branch,
        redis_client=redis_client,
        chat_id=chat_id,
        main_chat_id=workload_data.get("main_chat_id", ""),
        room_id=room_id,
        project_id=workload_data.get("project_id", ""),
        workload_title=workload_data.get("title", "Workload"),
    )

    # 6. Pre-register session so tool_approval can access it
    is_resume = bool(workload_data.get("session_id"))

    register_session(
        chat_id,
        {
            "session_type": "workload",
            "client": None,
            "task": None,
            "chat_id": chat_id,
            "member_id": workload_data["member_id"],
            "display_name": workload_data["display_name"],
            "room_id": room_id,
            "clone_path": clone_path,
            "project_id": workload_data.get("project_id", ""),
            "merge_state": merge_state,
            "branch_name": branch_name,
            "main_chat_id": workload_data.get("main_chat_id", ""),
            "workload_data": workload_data,
            "session_approvals": set(),
            "pending_approvals": {},
        },
    )

    can_use_tool = make_can_use_tool(
        session_key=chat_id,
        clone_path=clone_path,
        working_dir=str(worktree_path),
        session_state=_sessions[chat_id],
        redis_client=redis_client,
        chat_id=chat_id,
        member_id=workload_data["member_id"],
        display_name=workload_data["display_name"],
    )

    # Build a clean environment for the Claude CLI subprocess
    cli_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    cli_env["PLAYWRIGHT_MCP_SANDBOX"] = "false"
    cli_env["INTERNAL_API_KEY"] = settings.internal_api_key
    cli_env["API_BASE_URL"] = settings.api_service_url
    cli_env["AI_SERVICE_URL"] = "http://ai-service:8001"
    cli_env["AGENT_MEMBER_ID"] = workload_data["member_id"]

    # Per-agent git identity
    agent_name = workload_data["display_name"]
    agent_email = f"{agent_name.lower()}@team-agent"
    cli_env["GIT_AUTHOR_NAME"] = agent_name
    cli_env["GIT_COMMITTER_NAME"] = agent_name
    cli_env["GIT_AUTHOR_EMAIL"] = agent_email
    cli_env["GIT_COMMITTER_EMAIL"] = agent_email

    options = ClaudeAgentOptions(
        cwd=str(worktree_path),
        resume=workload_data.get("session_id") if is_resume else None,
        system_prompt=_build_system_prompt(agent_profile, workload_data),  # type: ignore[reportArgumentType]
        permission_mode=workload_data.get("permission_mode", "default"),
        disallowed_tools=["AskUserQuestion"],
        can_use_tool=can_use_tool,
        hooks={"Stop": [HookMatcher(hooks=[stop_hook])]},
        setting_sources=["project"],
        env=cli_env,
        include_partial_messages=True,
    )

    # 7. Connect
    try:
        client = ClaudeSDKClient(options)
        await client.connect()
    except Exception:
        logger.exception(
            "Failed to connect ClaudeSDKClient for workload %s", workload_id[:8]
        )
        unregister_session(chat_id)
        await update_chat_status(chat_id, "needs_attention")
        await publish_status_event(
            redis_client, chat_id, "needs_attention", room_id, chat_type="workload"
        )
        return

    # 8. Finish registration and start relay
    _sessions[chat_id]["client"] = client

    relay_task = asyncio.create_task(
        relay_messages(
            chat_id, client, redis_client, completion_status="needs_attention"
        ),
        name=f"workload-relay-{chat_id[:8]}",
    )
    _sessions[chat_id]["task"] = relay_task

    # 9. Send initial prompt (or skip if resuming)
    if not is_resume:
        initial_prompt = _build_initial_prompt(workload_data)
        await client.query(initial_prompt)
        logger.info("Sent initial prompt to workload %s", workload_id[:8])
    else:
        logger.info(
            "Resumed session %s for workload %s",
            workload_data["session_id"],
            workload_id[:8],
        )


async def shutdown_all_workload_sessions(redis_client: aioredis.Redis) -> None:
    """Gracefully stop all active workload sessions."""
    for session_key, session in list(_sessions.items()):
        if session.get("session_type") != "workload":
            continue
        chat_id = session.get("chat_id", session_key)
        logger.info("Shutting down workload session %s", chat_id[:8])
        await stop_session(chat_id, "needs_attention", redis_client)
