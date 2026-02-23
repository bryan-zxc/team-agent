"""Tool approval callback — bridges can_use_tool to the frontend via Redis."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)

# How long to wait for a human response before auto-denying.
APPROVAL_TIMEOUT_SECONDS = 300  # 5 minutes


# ── Project-level settings persistence ────────────────────────────────


def _read_project_allowed_tools(clone_path: str) -> list[str]:
    """Read the permissions.allow array from the project's .claude/settings.local.json."""
    settings_path = Path(clone_path) / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return []
    try:
        data = json.loads(settings_path.read_text())
        return data.get("permissions", {}).get("allow", [])
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read %s", settings_path)
        return []


def _write_project_allowed_tool(clone_path: str, permission_key: str) -> None:
    """Add a permission key to the project's .claude/settings.local.json."""
    settings_path = Path(clone_path) / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    permissions = data.setdefault("permissions", {})
    allow_list: list = permissions.setdefault("allow", [])
    if permission_key not in allow_list:
        allow_list.append(permission_key)

    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    logger.info("Persisted tool approval '%s' to %s", permission_key, settings_path)


# ── Permission key construction & matching ────────────────────────────


def _build_permission_key(
    tool_name: str,
    tool_input: dict[str, Any],
    suggestions: list[Any],
) -> str:
    """Build a Claude-Code-compatible permission key.

    Prefers the CLI's own suggestions when available (guaranteed format
    compatibility). Falls back to constructing from tool_name + input.
    """
    # Suggestions are PermissionUpdate dicts from the CLI.  Each has
    # ``rules`` → list of ``{tool_name: "Bash(git push:*)", ...}``.
    if suggestions:
        for suggestion in suggestions:
            rules = None
            if isinstance(suggestion, dict):
                rules = suggestion.get("rules")
            elif hasattr(suggestion, "rules"):
                rules = suggestion.rules
            if rules:
                for rule in rules:
                    key = None
                    if isinstance(rule, dict):
                        key = rule.get("tool_name")
                    elif hasattr(rule, "tool_name"):
                        key = rule.tool_name
                    if key:
                        return key

    # Fallback: construct from tool_name + input
    if tool_name == "Bash" and "command" in tool_input:
        cmd = tool_input["command"].strip()
        parts = cmd.split()
        prefix = " ".join(parts[:2]) if len(parts) >= 2 else parts[0] if parts else cmd
        return f"Bash({prefix}:*)"

    if tool_name in ("Write", "Edit", "MultiEdit", "Read", "Glob", "Grep"):
        return tool_name

    if tool_name == "WebFetch" and "url" in tool_input:
        try:
            from urllib.parse import urlparse
            domain = urlparse(tool_input["url"]).netloc
            if domain:
                return f"WebFetch(domain:{domain})"
        except Exception:
            pass
        return "WebFetch"

    return tool_name


def _tool_matches(
    tool_name: str,
    tool_input: dict[str, Any],
    allowed: list[str],
    suggestions: list[Any],
) -> bool:
    """Check whether the current tool call matches any entry in the allowed list."""
    permission_key = _build_permission_key(tool_name, tool_input, suggestions)

    for pattern in allowed:
        # Exact match
        if pattern == permission_key:
            return True

        # Bare tool name match (e.g. "Write" matches any Write call)
        if pattern == tool_name:
            return True

        # Wildcard: "Bash(git push:*)" should match "Bash(git push origin main)"
        if pattern.endswith(":*)"):
            prefix = pattern[:-2]  # "Bash(git push"
            if permission_key.startswith(prefix):
                return True

        # Glob: "Bash(*)" matches any Bash call
        if pattern == f"{tool_name}(*)":
            return True

    return False


# ── Tool input summarisation ──────────────────────────────────────────


def _summarise_tool_input(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Create a human-readable one-liner of what the tool wants to do."""
    if tool_name == "Bash" and "command" in tool_input:
        return tool_input["command"][:500]
    if tool_name in ("Write", "Edit", "MultiEdit") and "file_path" in tool_input:
        return tool_input["file_path"]
    if tool_name == "Read" and "file_path" in tool_input:
        return tool_input["file_path"]
    if tool_name == "Glob" and "pattern" in tool_input:
        return tool_input["pattern"]
    if tool_name == "Grep" and "pattern" in tool_input:
        return f'/{tool_input["pattern"]}/'
    if tool_name == "WebFetch" and "url" in tool_input:
        return tool_input["url"][:200]
    # Generic fallback
    keys = ", ".join(tool_input.keys())
    return f"{tool_name}({keys})"


# ── Original file content for diff view ───────────────────────────────


def _read_original_content(
    worktree_path: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str | None:
    """Read the current file content from the worktree for Write/Edit diff display."""
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None

    file_path = tool_input.get("file_path")
    if not file_path:
        return None

    # Resolve relative to worktree
    resolved = Path(worktree_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)
    if not resolved.exists():
        return ""  # New file — empty original

    try:
        return resolved.read_text(errors="replace")
    except OSError:
        logger.warning("Could not read original file %s for diff", resolved)
        return None


# ── Callback factory ──────────────────────────────────────────────────


def make_can_use_tool(
    workload_id: str,
    clone_path: str,
    worktree_path: str,
    session_state: dict,
    redis_client: Any,
    chat_id: str,
    member_id: str,
    display_name: str,
):
    """Create a ``can_use_tool`` callback closure for a workload session.

    ``session_state`` must contain:
      - ``session_approvals``: set[str]  — permission keys approved for this session
      - ``pending_approvals``: dict[str, asyncio.Future]  — request_id → Future
    """

    async def _callback(
        tool_name: str,
        tool_input: dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        suggestions = context.suggestions or []

        # 1. Check project-level persistent approvals
        project_allowed = _read_project_allowed_tools(clone_path)
        if _tool_matches(tool_name, tool_input, project_allowed, suggestions):
            return PermissionResultAllow()

        # 2. Check session-level in-memory approvals
        permission_key = _build_permission_key(tool_name, tool_input, suggestions)
        if permission_key in session_state["session_approvals"]:
            return PermissionResultAllow()

        # 3. Prompt the human via Redis → WebSocket
        approval_request_id = str(uuid.uuid4())
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        session_state["pending_approvals"][approval_request_id] = future

        input_summary = _summarise_tool_input(tool_name, tool_input)
        original_content = _read_original_content(worktree_path, tool_name, tool_input)

        request_msg = {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "member_id": member_id,
            "display_name": display_name,
            "type": "tool_approval_request",
            "content": json.dumps({
                "blocks": [{
                    "type": "tool_approval_request",
                    "approval_request_id": approval_request_id,
                    "workload_id": workload_id,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "input_summary": input_summary,
                    "permission_key": permission_key,
                    "original_content": original_content,
                }],
                "mentions": [],
            }),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis_client.publish("chat:responses", json.dumps(request_msg))
        logger.info(
            "Tool approval request %s for %s (workload %s)",
            approval_request_id[:8], tool_name, workload_id[:8],
        )

        # 4. Wait for human response
        try:
            decision = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "Tool approval timed out for %s (workload %s)",
                tool_name, workload_id[:8],
            )
            return PermissionResultDeny(
                message=f"Tool approval timed out after {APPROVAL_TIMEOUT_SECONDS}s. "
                        f"No human responded to the request to use {tool_name}.",
            )
        finally:
            session_state["pending_approvals"].pop(approval_request_id, None)

        # 5. Process the decision
        tier = decision["decision"]

        if tier == "deny":
            reason = decision.get("reason", "Denied by human reviewer.")
            return PermissionResultDeny(message=reason)

        if tier == "approve_session":
            session_state["session_approvals"].add(permission_key)

        if tier == "approve_project":
            session_state["session_approvals"].add(permission_key)
            _write_project_allowed_tool(clone_path, permission_key)

        # "approve", "approve_session", or "approve_project" all allow
        return PermissionResultAllow()

    return _callback


# ── Resolution (called from listener) ────────────────────────────────


def resolve_tool_approval(
    workload_id: str,
    approval_request_id: str,
    decision: dict,
) -> bool:
    """Resolve a pending tool approval Future.

    Returns True if resolved, False if no matching pending approval.
    """
    from .workload import _sessions

    session = _sessions.get(workload_id)
    if not session:
        logger.warning("No active session for workload %s", workload_id[:8])
        return False

    future = session.get("pending_approvals", {}).get(approval_request_id)
    if not future or future.done():
        logger.warning(
            "No pending approval %s for workload %s",
            approval_request_id[:8], workload_id[:8],
        )
        return False

    future.set_result(decision)
    return True
