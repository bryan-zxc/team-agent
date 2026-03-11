"""Shared session utilities — registry, relay loop, and SDK integration."""

import asyncio
import json
import logging
import uuid as uuid_mod
from datetime import datetime, timezone

import asyncpg
import httpx
import redis.asyncio as aioredis

from . import screencast
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import StreamEvent

from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)

_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Unified session registry: chat_id → {client, task, ...}
_sessions: dict[str, dict] = {}


# ── Registry ──────────────────────────────────────────────────────────


def register_session(session_key: str, session_dict: dict) -> None:
    """Register a session in the unified registry."""
    _sessions[session_key] = session_dict


def unregister_session(session_key: str) -> dict | None:
    """Remove a session from the registry, returning it (or None).

    Automatically rejects any pending tool approvals so blocked futures
    unblock cleanly instead of hanging indefinitely.
    """
    session = _sessions.pop(session_key, None)
    if session:
        _reject_pending_approvals(session, session_key)
    return session


def _reject_pending_approvals(session: dict, session_key: str) -> None:
    """Reject all pending tool approval futures in a session."""
    pending = session.get("pending_approvals", {})
    for req_id, future in pending.items():
        if not future.done():
            future.set_result({"decision": "deny", "reason": "Session interrupted"})
            logger.info(
                "Auto-denied pending approval %s (session %s)",
                req_id[:8],
                session_key[:8],
            )


# ── SDK content block conversion ──────────────────────────────────────


def convert_blocks(content_blocks: list) -> list[dict]:
    """Convert SDK content blocks to serialisable dicts."""
    blocks: list[dict] = []
    for block in content_blocks:
        if isinstance(block, TextBlock):
            blocks.append({"type": "text", "value": block.text})
        elif isinstance(block, ThinkingBlock):
            blocks.append({"type": "thinking", "thinking": block.thinking})
        elif isinstance(block, ToolUseBlock):
            blocks.append(
                {
                    "type": "tool_use",
                    "tool_use_id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
        elif isinstance(block, ToolResultBlock):
            blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                }
            )
    return blocks


# ── Token accumulation ────────────────────────────────────────────────


def accumulate_stream_tokens(event: dict, running_total: int) -> int:
    """Parse a raw Anthropic API stream event and return updated token total."""
    event_type = event.get("type")
    if event_type == "message_start":
        usage = event.get("message", {}).get("usage", {})
        running_total += usage.get("input_tokens", 0)
    elif event_type == "message_delta":
        usage = event.get("usage", {})
        running_total += usage.get("output_tokens", 0)
    return running_total


# ── Message publishing ────────────────────────────────────────────────


async def publish_message(
    redis_client: aioredis.Redis,
    chat_id: str,
    member_id: str,
    display_name: str,
    msg_type: str,
    blocks: list[dict],
) -> str:
    """Format and publish a message to chat:responses. Returns the message ID."""
    structured_content = json.dumps(
        {
            "blocks": blocks,
            "mentions": [],
        }
    )

    msg_id = str(uuid_mod.uuid4())
    response = {
        "id": msg_id,
        "chat_id": chat_id,
        "member_id": member_id,
        "display_name": display_name,
        "type": msg_type,
        "content": structured_content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_client.publish("chat:responses", json.dumps(response))
    return msg_id


# ── Heartbeat ─────────────────────────────────────────────────────────


def create_heartbeat(
    redis_client: aioredis.Redis,
    chat_id: str,
    session_key: str,
    get_tokens: callable,  # type: ignore[reportGeneralTypeIssues]
) -> tuple[callable, callable, callable]:  # type: ignore[reportGeneralTypeIssues]
    """Create heartbeat management functions.

    Returns (start, stop, restart) callables.
    ``get_tokens`` is a zero-arg callable returning the current token count.
    """
    heartbeat_holder: dict = {"task": None}
    session_state = _sessions.get(session_key, {})

    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(1)
                await redis_client.publish(
                    "chat:responses",
                    json.dumps(
                        {
                            "_event": "agent_activity",
                            "chat_id": session_key,
                            "phase": "processing",
                            "tokens": get_tokens(),
                        }
                    ),
                )
        except asyncio.CancelledError:
            pass

    def start():
        heartbeat_holder["task"] = asyncio.create_task(_heartbeat())
        session_state["heartbeat_task"] = heartbeat_holder["task"]

    def stop():
        task = heartbeat_holder["task"]
        if task and not task.done():
            task.cancel()
        heartbeat_holder["task"] = None
        session_state["heartbeat_task"] = None

    def restart():
        stop()
        start()

    # Expose restart callback so tool_approval can resume the heartbeat
    session_state["restart_heartbeat"] = start

    return start, stop, restart


# ── Chat status persistence ──────────────────────────────────────────


async def update_chat_status(
    chat_id: str,
    status: str,
    session_id: str | None = None,
) -> None:
    """Update status, updated_at, and optionally session_id on a chat record."""
    conn = await asyncpg.connect(_dsn)
    try:
        if session_id is not None:
            await conn.execute(
                "UPDATE chats SET status = $1, updated_at = $2, session_id = $3 WHERE id = $4",
                status,
                datetime.now(timezone.utc),
                session_id,
                uuid_mod.UUID(chat_id),
            )
        else:
            await conn.execute(
                "UPDATE chats SET status = $1, updated_at = $2 WHERE id = $3",
                status,
                datetime.now(timezone.utc),
                uuid_mod.UUID(chat_id),
            )
    finally:
        await conn.close()


# ── Status event publishing ──────────────────────────────────────────


async def publish_status_event(
    redis_client: aioredis.Redis,
    chat_id: str,
    status: str,
    room_id: str,
    **extra,
) -> None:
    """Publish a status change to the chat:status Redis channel."""
    event = {
        "chat_id": chat_id,
        "status": status,
        "room_id": room_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    await redis_client.publish("chat:status", json.dumps(event))


# ── Worktree cleanup ─────────────────────────────────────────────────


async def cleanup_worktree(clone_path: str, branch_name: str) -> None:
    """Remove a worktree and delete its branch.

    Derives the worktree path from clone_path and branch_name.
    Silently logs failures — cleanup is best-effort.
    """
    slug = branch_name.removeprefix("workload/")
    worktree_path = Path(clone_path).parent / "worktrees" / slug

    if worktree_path.exists():
        rc, _, err = await run_git(
            "worktree", "remove", str(worktree_path), "--force", cwd=clone_path
        )
        if rc != 0:
            logger.warning("Failed to remove worktree %s: %s", worktree_path, err)
        else:
            logger.info("Removed worktree %s", worktree_path)

    rc, _, err = await run_git("branch", "-D", branch_name, cwd=clone_path)
    if rc != 0:
        logger.warning("Failed to delete branch %s: %s", branch_name, err)
    else:
        logger.info("Deleted branch %s", branch_name)

    # Delete the remote branch (best-effort — it may not have been pushed)
    rc, _, err = await run_git(
        "push", "origin", "--delete", branch_name, cwd=clone_path
    )
    if rc != 0:
        logger.info(
            "Remote branch %s not deleted (may not exist): %s", branch_name, err
        )
    else:
        logger.info("Deleted remote branch %s", branch_name)


# ── Stop session ─────────────────────────────────────────────────────


async def stop_session(
    chat_id: str,
    target_status: str,
    redis_client: aioredis.Redis,
    *,
    purge: bool = False,
) -> bool:
    """Stop any session (workload or admin) and transition to the given status.

    Unregisters from the session registry, cancels the relay task,
    gracefully interrupts the SDK client to capture session_id for resume,
    updates the DB, and publishes status.

    When ``purge`` is True (used for cancel):
    - Sends a cancellation notice to the agent before interrupting
    - Does NOT capture session_id (cancel is final, no resume)
    - Removes the worktree and deletes the branch

    Returns True if a session was found and stopped.
    """
    session = unregister_session(chat_id)
    if not session:
        return False

    room_id = session.get("room_id", "")
    task = session.get("task")
    client = session.get("client")
    session_id = None

    # 1. Cancel relay task so it doesn't compete for messages
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    # 2. Notify agent + interrupt
    if client:
        if purge:
            # Send cancellation notice before interrupting
            try:
                await client.query(
                    "This workload has been cancelled. All data in the worktree "
                    "will be purged and all uncommitted work is lost."
                )
            except Exception:
                logger.debug(
                    "Could not send cancellation notice to session %s", chat_id[:8]
                )

        try:
            await client.interrupt()
            if not purge:
                # Only capture session_id when not purging (for potential resume)
                async with asyncio.timeout(5):
                    async for msg in client.receive_messages():
                        if isinstance(msg, ResultMessage):
                            session_id = msg.session_id
                            break
        except Exception:
            pass

        try:
            await client.disconnect()
        except Exception:
            logger.debug(
                "Expected disconnect error for session %s (cross-task scope)",
                chat_id[:8],
            )

    # 3. Purge worktree + branch if requested
    if purge:
        clone_path = session.get("clone_path")
        branch_name = session.get("branch_name")
        if clone_path and branch_name:
            await cleanup_worktree(clone_path, branch_name)

    await update_chat_status(chat_id, target_status, session_id=session_id)

    if room_id:
        await publish_status_event(
            redis_client,
            chat_id,
            target_status,
            room_id,
            chat_type=session.get("session_type"),
        )

    logger.info(
        "Stopped session %s → %s (session_id: %s, purged: %s)",
        chat_id[:8],
        target_status,
        session_id or "none",
        purge,
    )
    return True


# ── Coordinator lookup ────────────────────────────────────────────────


async def get_coordinator_for_chat(chat_id: str) -> dict:
    """Look up the coordinator member for the project owning a chat."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT pm.id, pm.display_name "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN project_members pm ON pm.project_id = r.project_id "
            "WHERE c.id = $1 AND pm.type = 'coordinator'",
            uuid_mod.UUID(chat_id),
        )
        if not row:
            raise ValueError(f"No coordinator found for chat {chat_id}")
        return {"id": str(row["id"]), "display_name": row["display_name"]}
    finally:
        await conn.close()


# ── Git subprocess ────────────────────────────────────────────────────


async def run_git(*args: str, cwd: str) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


# ── Route message to active session ───────────────────────────────────


async def route_message(session_key: str, prompt: str) -> bool:
    """Route a follow-up message to an active session.

    Returns True if delivered, False if no active session.
    """
    session = _sessions.get(session_key)
    if not session:
        return False

    client = session["client"]
    await client.query(prompt)
    logger.info("Routed follow-up message to session %s", session_key[:8])
    return True


# ── Shared relay loop ─────────────────────────────────────────────────


async def relay_messages(
    session_key: str,
    client,
    redis_client: aioredis.Redis,
    completion_status: str = "needs_attention",
) -> None:
    """Relay messages from ClaudeSDKClient to Redis chat:responses.

    Shared between workload and admin sessions. Reads session data
    (chat_id, member_id, display_name, room_id, project_id) from the
    unified session registry.

    ``completion_status`` controls what status the chat transitions to
    on ResultMessage: "needs_attention" for workloads, "completed" for admin.
    """
    session = _sessions.get(session_key)
    if not session:
        logger.error("No session registered for key %s", session_key[:8])
        return

    chat_id = session["chat_id"]
    member_id = session["member_id"]
    display_name = session["display_name"]
    room_id = session.get("room_id", "")
    project_id = session.get("project_id")

    # Token accumulator
    total_tokens = 0

    def get_tokens():
        return total_tokens

    start_heartbeat, stop_heartbeat, restart_heartbeat = create_heartbeat(
        redis_client,
        chat_id,
        session_key,
        get_tokens,
    )

    # Track tool_use_ids of playwright-cli open commands for screencast triggering
    pending_playwright_opens: set[str] = set()

    try:
        start_heartbeat()

        async for msg in client.receive_messages():
            if isinstance(msg, StreamEvent):
                event = msg.event
                total_tokens = accumulate_stream_tokens(event, total_tokens)
                continue

            if isinstance(msg, AssistantMessage):
                stop_heartbeat()

                blocks = convert_blocks(msg.content)

                # Detect playwright-cli open commands for live view
                for block in msg.content:
                    if isinstance(block, ToolUseBlock) and block.name == "Bash":
                        cmd = (
                            block.input.get("command", "")
                            if isinstance(block.input, dict)
                            else ""
                        )
                        if "playwright-cli open" in cmd:
                            logger.info(
                                "Detected playwright-cli open for session %s: %s",
                                session_key[:8],
                                cmd[:100],
                            )
                            pending_playwright_opens.add(block.id)

                if not blocks:
                    start_heartbeat()
                    continue

                structured_content = json.dumps(
                    {
                        "blocks": blocks,
                        "mentions": [],
                    }
                )

                response = {
                    "id": str(uuid_mod.uuid4()),
                    "chat_id": chat_id,
                    "member_id": member_id,
                    "display_name": display_name,
                    "type": "ai",
                    "content": structured_content,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await redis_client.publish("chat:responses", json.dumps(response))

                start_heartbeat()

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
                                logger.info(
                                    "Launching screencast for session %s, room_id=%s",
                                    session_key[:8],
                                    room_id,
                                )
                                screencast.launch_screencast(
                                    chat_id,
                                    room_id,
                                    redis_client,
                                    owner_name=display_name,
                                )

                    blocks = convert_blocks(msg.content)
                    result_blocks = [b for b in blocks if b["type"] == "tool_result"]
                    if result_blocks:
                        structured_content = json.dumps(
                            {
                                "blocks": result_blocks,
                                "mentions": [],
                            }
                        )
                        response = {
                            "id": str(uuid_mod.uuid4()),
                            "chat_id": chat_id,
                            "member_id": member_id,
                            "display_name": display_name,
                            "type": "ai",
                            "content": structured_content,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                        await redis_client.publish(
                            "chat:responses", json.dumps(response)
                        )

            elif isinstance(msg, ResultMessage):
                stop_heartbeat()

                logger.info(
                    "Session %s completed (session_id: %s, error: %s, turns: %d, cost: %s)",
                    session_key[:8],
                    msg.session_id,
                    msg.is_error,
                    msg.num_turns,
                    f"${msg.total_cost_usd:.4f}" if msg.total_cost_usd else "n/a",
                )

                # Persist SDK session cost
                if msg.total_cost_usd is not None:
                    try:
                        from .cost import get_cost_tracker

                        await get_cost_tracker().track_sdk_cost(
                            total_cost_usd=msg.total_cost_usd,
                            model="claude-opus-4",
                            usage=msg.usage,
                            caller="claude_sdk",
                            session_id=msg.session_id,
                            num_turns=msg.num_turns,
                            duration_ms=msg.duration_ms,
                            member_id=member_id,
                            project_id=project_id,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to track SDK cost for session %s",
                            session_key[:8],
                        )

                # Update chat status and session_id
                # If escalation already set "investigating", preserve it
                merge_state = session.get("merge_state")
                escalated = (
                    merge_state is not None and merge_state.get("succeeded") is False
                )
                final_status = "investigating" if escalated else completion_status

                await update_chat_status(
                    chat_id, final_status, session_id=msg.session_id
                )

                await publish_status_event(
                    redis_client,
                    chat_id,
                    final_status,
                    room_id,
                    chat_type=session.get("session_type"),
                )

                # Workload-only: post merge summary to main chat
                if merge_state is not None:
                    main_chat_id = session.get("main_chat_id", "")
                    workload_title = session.get("workload_data", {}).get(
                        "title", "Workload"
                    )
                    merge_succeeded = merge_state.get("succeeded")

                    if merge_succeeded is True:
                        merged_to = merge_state.get("target_branch", "main")
                        summary = (
                            f"Workload **{workload_title}** has finished "
                            f"and its changes have been merged to {merged_to}."
                        )
                    elif merge_succeeded is False:
                        branch = session.get("branch_name", "unknown")
                        summary = (
                            f"Workload **{workload_title}** has finished "
                            f"but merge conflicts could not be resolved automatically. "
                            f"Changes remain on branch `{branch}`."
                        )
                    else:
                        summary = (
                            f"Workload **{workload_title}** has finished "
                            f"and needs attention."
                        )

                    if msg.result:
                        summary += f"\n\nSummary: {msg.result}"

                    # If escalation was triggered, append notice and link
                    admin_chat_id = merge_state.get("admin_chat_id")
                    if admin_chat_id:
                        summary += "\n\nI'm looking into it."

                    blocks: list[dict] = [{"type": "text", "value": summary}]
                    if admin_chat_id:
                        blocks.append(
                            {
                                "type": "link",
                                "url": f"/admin/chats/{admin_chat_id}",
                                "label": "View \u2192",
                            }
                        )

                    coordinator = await get_coordinator_for_chat(main_chat_id)
                    await publish_message(
                        redis_client,
                        main_chat_id,
                        coordinator["id"],
                        coordinator["display_name"],
                        "coordinator",
                        blocks,
                    )

                # Post-completion manifest check
                if project_id and (merge_state is None or merge_state.get("succeeded")):
                    try:
                        pull = "false" if merge_state else "true"
                        _headers = {"x-internal-key": settings.internal_api_key}
                        async with httpx.AsyncClient(
                            timeout=10.0, headers=_headers
                        ) as http:
                            resp = await http.post(
                                f"{settings.api_service_url}/projects/"
                                f"{project_id}/check-manifest?pull={pull}",
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get("is_locked"):
                                    logger.warning(
                                        "Session %s: manifest check triggered lockdown",
                                        session_key[:8],
                                    )
                            else:
                                logger.warning(
                                    "Session %s: manifest check returned %d",
                                    session_key[:8],
                                    resp.status_code,
                                )
                    except Exception:
                        logger.warning(
                            "Session %s: manifest check failed (non-blocking)",
                            session_key[:8],
                            exc_info=True,
                        )

                await screencast.stop_screencast(chat_id)
                unregister_session(session_key)
                return

    except asyncio.CancelledError:
        logger.info("Relay task cancelled for session %s", session_key[:8])
        stop_heartbeat()
        await screencast.stop_screencast(chat_id)
        unregister_session(session_key)
    except Exception:
        logger.exception("Relay task error for session %s", session_key[:8])
        stop_heartbeat()
        await screencast.stop_screencast(chat_id)

        # Escalate workload relay crashes to admin room
        session_type = session.get("session_type") if session else None
        if session_type == "workload" and session:
            try:
                import traceback as tb_mod
                from .escalation import escalate_to_admin

                await escalate_to_admin(
                    redis_client,
                    project_id=session.get("project_id", ""),
                    clone_path=session.get("clone_path", ""),
                    workload_chat_id=chat_id,
                    workload_title=session.get("workload_data", {}).get(
                        "title", "Workload"
                    ),
                    main_chat_id=session.get("main_chat_id", ""),
                    room_id=room_id,
                    error_type="relay_crash",
                    error_details=tb_mod.format_exc(),
                )
            except Exception:
                logger.exception(
                    "Failed to escalate relay crash for session %s", session_key[:8]
                )
        else:
            # Non-workload (admin) relay crash — just set needs_attention
            try:
                await update_chat_status(chat_id, "needs_attention")
                await publish_status_event(
                    redis_client,
                    chat_id,
                    "needs_attention",
                    room_id,
                    chat_type=session_type,
                )
            except Exception:
                logger.exception("Failed to update chat status to needs_attention")

        unregister_session(session_key)
