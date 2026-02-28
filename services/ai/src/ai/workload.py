"""Workload session management — worktree creation, SDK client lifecycle, and message relay."""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx
import redis.asyncio as aioredis

from . import screencast
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .config import settings
from .tool_approval import make_can_use_tool

logger = logging.getLogger(__name__)

_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Session registry: workload_id → {client, task, workload_data}
_sessions: dict[str, dict] = {}


async def fetch_workload_data_for_resume(workload_id: str) -> dict | None:
    """Fetch full workload data from DB for session resume.

    Returns the workload_data dict compatible with start_workload_session(),
    or None if the workload is not found or has no session_id.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT w.id, w.title, w.description, w.status, w.session_id, "
            "w.member_id, w.main_chat_id, "
            "c.id AS chat_id, c.room_id, "
            "pm.display_name, "
            "p.clone_path "
            "FROM workloads w "
            "JOIN chats c ON c.workload_id = w.id AND c.type = 'workload' "
            "JOIN project_members pm ON pm.id = w.member_id "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN projects p ON p.id = r.project_id "
            "WHERE w.id = $1",
            uuid.UUID(workload_id),
        )
        if not row or not row["session_id"]:
            return None

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
            # Not needed for resume (initial prompt is skipped)
            "background_context": None,
            "problem": None,
        }
    finally:
        await conn.close()


async def _publish_status(
    redis_client: aioredis.Redis,
    workload_id: str,
    status: str,
    room_id: str,
) -> None:
    """Broadcast a workload status change to the workload:status Redis channel."""
    await redis_client.publish(
        "workload:status",
        json.dumps({
            "workload_id": workload_id,
            "status": status,
            "room_id": room_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }),
    )


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


async def _run_git(*args: str, cwd: str) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


_MAX_MERGE_RETRIES = 2


def _make_stop_hook(
    workload_id: str,
    clone_path: str,
    worktree_path: Path,
    branch_name: str,
    display_name: str,
    target_branch: str,
) -> tuple:
    """Create a Stop hook that merges the workload branch into the project's default branch.

    Returns (hook_callback, merge_state_dict).
    The merge_state dict is shared with the relay handler to report merge outcome.
    """
    merge_state: dict = {"succeeded": None, "retries": 0, "target_branch": target_branch}

    async def stop_hook(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> HookJSONOutput:
        # If worktree is already gone, nothing to merge — let agent stop
        if not worktree_path.exists():
            logger.info("Workload %s: worktree already removed, skipping merge", workload_id[:8])
            merge_state["succeeded"] = True
            return {"continue_": False}

        retries = merge_state["retries"]

        if retries >= _MAX_MERGE_RETRIES:
            logger.warning(
                "Workload %s: merge failed after %d retries, giving up",
                workload_id[:8], retries,
            )
            merge_state["succeeded"] = False
            return {
                "continue_": False,
                "stopReason": (
                    f"Merge failed after {retries} attempts. "
                    f"Branch '{branch_name}' is preserved for manual resolution."
                ),
            }

        # Auto-commit any uncommitted changes in the worktree
        # (the agent runs with acceptEdits — it can write files but not git commit)
        await _run_git("add", "-A", cwd=str(worktree_path))
        status_rc, status_out, _ = await _run_git("status", "--porcelain", cwd=str(worktree_path))
        if status_rc == 0 and status_out.strip():
            commit_rc, _, commit_err = await _run_git(
                "-c", f"user.name={display_name}",
                "-c", f"user.email={display_name.lower()}@team-agent",
                "commit", "-m", f"Workload {workload_id[:8]}: auto-commit changes",
                cwd=str(worktree_path),
            )
            if commit_rc == 0:
                logger.info("Workload %s: auto-committed uncommitted changes", workload_id[:8])
            else:
                logger.warning("Workload %s: auto-commit failed: %s", workload_id[:8], commit_err)

        # Attempt merge into main
        rc, stdout, stderr = await _run_git(
            "merge", branch_name, "--no-edit",
            cwd=clone_path,
        )

        if rc == 0:
            logger.info("Workload %s: merge succeeded on attempt %d", workload_id[:8], retries + 1)

            # Clean up worktree and branch
            await _run_git("worktree", "remove", str(worktree_path), "--force", cwd=clone_path)
            await _run_git("branch", "-d", branch_name, cwd=clone_path)

            # Push merged changes to remote
            push_rc, _, push_err = await _run_git("push", cwd=clone_path)
            if push_rc != 0:
                logger.warning("Workload %s: post-merge push failed: %s", workload_id[:8], push_err)
            else:
                logger.info("Workload %s: pushed merged changes to remote", workload_id[:8])

            merge_state["succeeded"] = True
            return {"continue_": False}

        # Merge conflict — abort and ask agent to rebase
        logger.warning(
            "Workload %s: merge conflict on attempt %d: %s",
            workload_id[:8], retries + 1, stderr,
        )
        await _run_git("merge", "--abort", cwd=clone_path)
        merge_state["retries"] = retries + 1

        return {
            "continue_": True,
            "reason": (
                f"Your branch '{branch_name}' has merge conflicts with {target_branch} "
                f"(attempt {retries + 1} of {_MAX_MERGE_RETRIES}). "
                f"Please rebase onto {target_branch} and resolve the conflicts:\n\n"
                f"1. Run: git rebase {target_branch}\n"
                f"2. Resolve any conflicts in the affected files\n"
                f"3. Run: git rebase --continue\n"
                f"4. Then finish your task as normal."
            ),
        }

    return stop_hook, merge_state


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

    # Periodic heartbeat for activity indicator
    turn_count = 0

    async def _heartbeat():
        """Send periodic agent_activity events while the SDK is generating."""
        try:
            while True:
                await asyncio.sleep(1)
                await redis_client.publish("chat:responses", json.dumps({
                    "_event": "agent_activity",
                    "chat_id": chat_id,
                    "workload_id": workload_id,
                    "phase": "processing",
                    "tokens": turn_count,
                }))
        except asyncio.CancelledError:
            pass

    heartbeat_task: asyncio.Task | None = None
    session_state = _sessions.get(workload_id, {})

    def _convert_blocks(content_blocks: list) -> list[dict]:
        """Convert SDK content blocks to serialisable dicts."""
        blocks: list[dict] = []
        for block in content_blocks:
            if isinstance(block, TextBlock):
                blocks.append({"type": "text", "value": block.text})
            elif isinstance(block, ThinkingBlock):
                blocks.append({"type": "thinking", "thinking": block.thinking})
            elif isinstance(block, ToolUseBlock):
                blocks.append({
                    "type": "tool_use",
                    "tool_use_id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif isinstance(block, ToolResultBlock):
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                })
        return blocks

    def _start_heartbeat():
        nonlocal heartbeat_task
        heartbeat_task = asyncio.create_task(_heartbeat())
        session_state["heartbeat_task"] = heartbeat_task

    def _stop_heartbeat():
        nonlocal heartbeat_task
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        session_state["heartbeat_task"] = None

    # Expose restart callback so tool_approval can resume the heartbeat
    session_state["restart_heartbeat"] = _start_heartbeat

    # Track tool_use_ids of playwright-cli open commands for screencast triggering
    pending_playwright_opens: set[str] = set()

    try:
        # Start heartbeat before the message loop
        _start_heartbeat()

        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                # Stop heartbeat while processing a complete message
                _stop_heartbeat()

                turn_count += 1
                blocks = _convert_blocks(msg.content)

                # Detect playwright-cli open commands for live view
                for block in msg.content:
                    if isinstance(block, ToolUseBlock) and block.name == "Bash":
                        cmd = block.input.get("command", "") if isinstance(block.input, dict) else ""
                        if "playwright-cli open" in cmd:
                            logger.info(
                                "Detected playwright-cli open for workload %s: %s",
                                workload_id[:8], cmd[:100],
                            )
                            pending_playwright_opens.add(block.id)

                if not blocks:
                    # Restart heartbeat for the next turn
                    _start_heartbeat()
                    continue

                structured_content = json.dumps({
                    "blocks": blocks,
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

                # Restart heartbeat for the next turn
                _start_heartbeat()

            elif isinstance(msg, UserMessage):
                # Relay tool results (user-role messages containing ToolResultBlock)
                if isinstance(msg.content, list):
                    # Check if a playwright-cli open just completed — start screencast
                    for block in msg.content:
                        if (
                            isinstance(block, ToolResultBlock)
                            and block.tool_use_id in pending_playwright_opens
                        ):
                            pending_playwright_opens.discard(block.tool_use_id)
                            if not block.is_error:
                                room_id = workload_data.get("room_id", "")
                                logger.info(
                                    "Launching screencast for workload %s, room_id=%s",
                                    workload_id[:8], room_id,
                                )
                                screencast.launch_screencast(
                                    workload_id, room_id, redis_client,
                                    owner_name=workload_data.get("display_name", ""),
                                )

                    blocks = _convert_blocks(msg.content)
                    result_blocks = [b for b in blocks if b["type"] == "tool_result"]
                    if result_blocks:
                        structured_content = json.dumps({
                            "blocks": result_blocks,
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
                _stop_heartbeat()

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

                await _publish_status(
                    redis_client, workload_id, "needs_attention",
                    workload_data.get("room_id", ""),
                )

                # Publish merge-aware summary to main chat
                session = _sessions.get(workload_id, {})
                merge_succeeded = session.get("merge_state", {}).get("succeeded")

                if merge_succeeded is True:
                    merged_to = session.get("merge_state", {}).get("target_branch", "main")
                    summary = (
                        f"Workload **{workload_data['title']}** has finished "
                        f"and its changes have been merged to {merged_to}."
                    )
                elif merge_succeeded is False:
                    branch = session.get("branch_name", "unknown")
                    summary = (
                        f"Workload **{workload_data['title']}** has finished "
                        f"but merge conflicts could not be resolved automatically. "
                        f"Changes remain on branch `{branch}`."
                    )
                else:
                    summary = (
                        f"Workload **{workload_data['title']}** has finished "
                        f"and needs attention."
                    )

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

                # Post-workload manifest check (no git pull — we just pushed)
                if merge_succeeded and workload_data.get("project_id"):
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as http:
                            resp = await http.post(
                                f"{settings.api_service_url}/projects/"
                                f"{workload_data['project_id']}/check-manifest?pull=false",
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get("is_locked"):
                                    logger.warning(
                                        "Workload %s: manifest check triggered lockdown",
                                        workload_id[:8],
                                    )
                            else:
                                logger.warning(
                                    "Workload %s: manifest check returned %d",
                                    workload_id[:8], resp.status_code,
                                )
                    except Exception:
                        logger.warning(
                            "Workload %s: manifest check failed (non-blocking)",
                            workload_id[:8], exc_info=True,
                        )

                await screencast.stop_screencast(workload_id)
                _sessions.pop(workload_id, None)
                return

    except asyncio.CancelledError:
        logger.info("Relay task cancelled for workload %s", workload_id[:8])
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        await screencast.stop_screencast(workload_id)
        _sessions.pop(workload_id, None)
    except Exception:
        logger.exception("Relay task error for workload %s", workload_id[:8])
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        await screencast.stop_screencast(workload_id)
        try:
            conn = await asyncpg.connect(_dsn)
            try:
                await conn.execute(
                    "UPDATE workloads SET status = 'needs_attention', updated_at = $1 WHERE id = $2",
                    datetime.now(timezone.utc), uuid.UUID(workload_id),
                )
            finally:
                await conn.close()
            await _publish_status(
                redis_client, workload_id, "needs_attention",
                workload_data.get("room_id", ""),
            )
        except Exception:
            logger.exception("Failed to update workload status to needs_attention")
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
                "UPDATE workloads SET status = 'needs_attention', updated_at = $1 WHERE id = $2",
                datetime.now(timezone.utc), uuid.UUID(workload_id),
            )
        finally:
            await conn.close()
        await _publish_status(
            redis_client, workload_id, "needs_attention",
            workload_data.get("room_id", ""),
        )
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

    await _publish_status(redis_client, workload_id, "running", workload_data.get("room_id", ""))

    # 3. Load agent profile for system prompt
    profile_path = Path(clone_path) / ".team-agent" / "agents" / f"{workload_data['display_name'].lower()}.md"
    agent_profile = profile_path.read_text() if profile_path.exists() else ""

    # 4. Read target branch from clone (whatever is checked out)
    _, target_branch_out, _ = await _run_git(
        "symbolic-ref", "--short", "HEAD", cwd=clone_path,
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
    )

    # 6. Build SDK options
    is_resume = bool(workload_data.get("session_id"))

    # Pre-register session so tool_approval can access it via _sessions
    _sessions[workload_id] = {
        "client": None,
        "task": None,
        "workload_data": workload_data,
        "merge_state": merge_state,
        "branch_name": branch_name,
        "clone_path": clone_path,
        "session_approvals": set(),
        "pending_approvals": {},
    }

    can_use_tool = make_can_use_tool(
        workload_id=workload_id,
        clone_path=clone_path,
        worktree_path=str(worktree_path),
        session_state=_sessions[workload_id],
        redis_client=redis_client,
        chat_id=workload_data["chat_id"],
        member_id=workload_data["member_id"],
        display_name=workload_data["display_name"],
    )

    # Build a clean environment for the Claude CLI subprocess:
    # - Strip ANTHROPIC_API_KEY so it uses the subscription OAuth token
    # - Set PLAYWRIGHT_MCP_SANDBOX=false so playwright-cli can run headless in Docker
    cli_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    cli_env["PLAYWRIGHT_MCP_SANDBOX"] = "false"

    # Per-agent git identity — env vars override all config levels
    agent_name = workload_data["display_name"]
    agent_email = f"{agent_name.lower()}@team-agent"
    cli_env["GIT_AUTHOR_NAME"] = agent_name
    cli_env["GIT_COMMITTER_NAME"] = agent_name
    cli_env["GIT_AUTHOR_EMAIL"] = agent_email
    cli_env["GIT_COMMITTER_EMAIL"] = agent_email

    options = ClaudeAgentOptions(
        cwd=str(worktree_path),
        resume=workload_data.get("session_id") if is_resume else None,
        system_prompt=_build_system_prompt(agent_profile, workload_data),
        permission_mode="default",
        can_use_tool=can_use_tool,
        hooks={"Stop": [HookMatcher(hooks=[stop_hook])]},
        setting_sources=["project"],
        env=cli_env,
    )

    # 6. Connect
    try:
        client = ClaudeSDKClient(options)
        await client.connect()
    except Exception:
        logger.exception("Failed to connect ClaudeSDKClient for workload %s", workload_id[:8])
        _sessions.pop(workload_id, None)
        conn = await asyncpg.connect(_dsn)
        try:
            await conn.execute(
                "UPDATE workloads SET status = 'needs_attention', updated_at = $1 WHERE id = $2",
                datetime.now(timezone.utc), uuid.UUID(workload_id),
            )
        finally:
            await conn.close()
        await _publish_status(
            redis_client, workload_id, "needs_attention",
            workload_data.get("room_id", ""),
        )
        return

    # 7. Finish registration and start relay
    _sessions[workload_id]["client"] = client

    relay_task = asyncio.create_task(
        _relay_messages(workload_id, client, workload_data, redis_client),
        name=f"workload-relay-{workload_id[:8]}",
    )
    _sessions[workload_id]["task"] = relay_task

    # 8. Send initial prompt (or skip if resuming)
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


async def stop_workload_session(
    workload_id: str,
    target_status: str,
    redis_client: aioredis.Redis,
) -> bool:
    """Stop a workload session and transition to the given status.

    Aborts the SDK session if running, updates the DB, and publishes the
    status change. Returns True if the workload was found and updated.
    """
    session = _sessions.pop(workload_id, None)
    room_id = ""

    if session:
        room_id = session.get("workload_data", {}).get("room_id", "")
        task = session.get("task")
        if task and not task.done():
            task.cancel()
        client = session.get("client")
        if client:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Error disconnecting workload %s during stop", workload_id[:8])

    # Update DB status regardless of whether a session was active
    conn = await asyncpg.connect(_dsn)
    try:
        result = await conn.execute(
            "UPDATE workloads SET status = $1, updated_at = $2 WHERE id = $3",
            target_status, datetime.now(timezone.utc), uuid.UUID(workload_id),
        )
        if result == "UPDATE 0":
            return False

        # If we didn't get room_id from session, look it up from DB
        if not room_id:
            row = await conn.fetchrow(
                "SELECT c.room_id FROM workloads w "
                "JOIN chats c ON c.workload_id = w.id "
                "WHERE w.id = $1",
                uuid.UUID(workload_id),
            )
            if row:
                room_id = str(row["room_id"])
    finally:
        await conn.close()

    if room_id:
        await _publish_status(redis_client, workload_id, target_status, room_id)

    logger.info("Stopped workload %s → %s", workload_id[:8], target_status)
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
