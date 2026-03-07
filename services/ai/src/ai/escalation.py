"""Escalation utility — auto-trigger admin room sessions for mechanical errors."""

import json
import logging
from pathlib import Path

import httpx
import redis.asyncio as aioredis

from .admin import fetch_admin_chat_data, start_admin_session
from .config import settings
from .session import (
    publish_status_event,
    route_message,
    update_chat_status,
)

logger = logging.getLogger(__name__)

_ESCALATION_DIR = Path("/tmp/team-agent-escalations")


async def _dump_chat_messages(chat_id: str) -> str | None:
    """Fetch chat messages from the API and write them to a markdown file.

    Returns the file path, or None on failure.
    """
    headers = {"x-internal-key": settings.internal_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as http:
            resp = await http.get(
                f"{settings.api_service_url}/chats/{chat_id}/messages"
            )
            if resp.status_code != 200:
                logger.warning(
                    "Failed to fetch messages for chat %s: %d",
                    chat_id[:8],
                    resp.status_code,
                )
                return None

        messages = resp.json()
        _ESCALATION_DIR.mkdir(parents=True, exist_ok=True)
        md_path = _ESCALATION_DIR / f"{chat_id}.md"

        lines = [f"# Chat transcript for {chat_id}\n"]
        for msg in messages:
            name = msg.get("display_name", "Unknown")
            msg_type = msg.get("type", "")
            created = msg.get("created_at", "")
            content = msg.get("content", "")

            # Try to extract text from structured content
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "blocks" in data:
                    text_parts = []
                    for block in data["blocks"]:
                        if block.get("type") == "text":
                            text_parts.append(block.get("value", ""))
                        elif block.get("type") == "tool_use":
                            text_parts.append(f"[Tool: {block.get('name', '?')}]")
                        elif block.get("type") == "tool_result":
                            text_parts.append("[Tool result]")
                    content = "\n".join(text_parts) if text_parts else content
            except (json.JSONDecodeError, TypeError):
                pass

            lines.append(f"**{name}** ({msg_type}) — {created}")
            lines.append(content)
            lines.append("")

        md_path.write_text("\n".join(lines))
        logger.info("Dumped chat messages to %s", md_path)
        return str(md_path)

    except Exception:
        logger.warning(
            "Failed to dump chat messages for %s", chat_id[:8], exc_info=True
        )
        return None


def _build_context_prompt(
    error_type: str,
    error_details: str,
    extra_context: dict,
    md_file_path: str | None,
) -> str:
    """Build the initial context message for the admin session."""
    parts = []

    if error_type == "merge_conflict":
        parts.append(
            f"I need to resolve a merge conflict for workload "
            f'"{extra_context.get("workload_title", "Unknown")}".'
        )
        parts.append(f"\n**Error:**\n```\n{error_details}\n```")
        parts.append(
            f"**Worktree:** `{extra_context.get('worktree_path', '?')}` "
            f"(branch: `{extra_context.get('branch_name', '?')}`)"
        )
        parts.append(
            f"**Target branch:** `{extra_context.get('target_branch', 'main')}`"
        )
        parts.append(f"**Clone path:** `{extra_context.get('clone_path', '?')}`")
        parts.append(
            f"**Workload chat ID:** `{extra_context.get('workload_chat_id', '?')}`"
        )

    elif error_type == "push_failure":
        parts.append(
            f"I need to resolve a push failure for workload "
            f'"{extra_context.get("workload_title", "Unknown")}".'
        )
        parts.append(f"\n**Error:**\n```\n{error_details}\n```")
        parts.append(f"**Clone path:** `{extra_context.get('clone_path', '?')}`")
        parts.append(
            f"**Workload chat ID:** `{extra_context.get('workload_chat_id', '?')}`"
        )

    elif error_type == "worktree_failure":
        parts.append(
            f"I couldn't create a worktree for workload "
            f'"{extra_context.get("workload_title", "Unknown")}".'
        )
        parts.append(f"\n**Error:**\n```\n{error_details}\n```")
        parts.append(f"**Clone path:** `{extra_context.get('clone_path', '?')}`")
        parts.append(f"**Attempted branch:** `{extra_context.get('branch_name', '?')}`")
        parts.append(
            f"**Workload chat ID:** `{extra_context.get('workload_chat_id', '?')}`"
        )

    elif error_type == "relay_crash":
        parts.append(
            f"The relay task crashed for workload "
            f'"{extra_context.get("workload_title", "Unknown")}".'
        )
        parts.append(f"\n**Traceback:**\n```\n{error_details}\n```")
        parts.append(
            f"**Workload chat ID:** `{extra_context.get('workload_chat_id', '?')}`"
        )

    if md_file_path:
        parts.append(f"\n**Chat transcript:** `{md_file_path}`")

    parts.append("\nUse the `/workload-recovery` skill to resolve this.")
    return "\n".join(parts)


async def escalate_to_admin(
    redis_client: aioredis.Redis,
    project_id: str,
    clone_path: str,
    workload_chat_id: str,
    workload_title: str,
    main_chat_id: str,
    room_id: str,
    error_type: str,
    error_details: str,
    extra_context: dict | None = None,
) -> str | None:
    """Escalate a mechanical error to the admin room.

    Creates an admin chat and starts an admin session with full context.
    The coordinator message in the main chat is posted by the session
    completion handler (which includes a link to this admin chat).

    Returns the admin chat_id on success, None on failure.
    """
    extra = extra_context or {}
    extra.setdefault("workload_title", workload_title)
    extra.setdefault("workload_chat_id", workload_chat_id)
    extra.setdefault("clone_path", clone_path)

    try:
        # 1. Dump chat messages to markdown file
        md_file_path = await _dump_chat_messages(workload_chat_id)

        # 2. Transition workload to investigating
        await update_chat_status(workload_chat_id, "investigating")
        await publish_status_event(
            redis_client,
            workload_chat_id,
            "investigating",
            room_id,
            chat_type="workload",
        )

        # 3. Create admin chat via API
        headers = {"x-internal-key": settings.internal_api_key}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as http:
            resp = await http.post(
                f"{settings.api_service_url}/projects/{project_id}/admin-room/chats",
                json={
                    "permission_mode": "acceptEdits",
                    "title": f"Escalation: {workload_title}",
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "Failed to create admin chat for escalation: %d %s",
                    resp.status_code,
                    resp.text,
                )
                return None

        admin_chat = resp.json()
        admin_chat_id = admin_chat["id"]
        logger.info(
            "Created admin chat %s for escalation (%s)", admin_chat_id[:8], error_type
        )

        # 4. Start admin session
        chat_data = await fetch_admin_chat_data(admin_chat_id)
        if not chat_data:
            logger.error("Failed to fetch admin chat data for %s", admin_chat_id[:8])
            return None

        await start_admin_session(chat_data, redis_client)

        # 5. Send context prompt to the admin session
        context_prompt = _build_context_prompt(
            error_type, error_details, extra, md_file_path
        )
        delivered = await route_message(admin_chat_id, context_prompt)
        if not delivered:
            logger.warning(
                "Failed to deliver context prompt to admin session %s",
                admin_chat_id[:8],
            )

        logger.info(
            "Escalated %s to admin room (admin chat %s, workload chat %s)",
            error_type,
            admin_chat_id[:8],
            workload_chat_id[:8],
        )
        return admin_chat_id

    except Exception:
        logger.exception(
            "Failed to escalate %s for workload chat %s",
            error_type,
            workload_chat_id[:8],
        )
        return None
