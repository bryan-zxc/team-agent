import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from .admin import fetch_admin_chat_data, start_admin_session
from .agents import generate_agent_profile
from .config import settings
from .cost import set_cost_context
from .runner import run_agent
from .session import route_message
from .tool_approval import resolve_tool_approval
from .workload import fetch_workload_data_for_resume, start_workload_session

logger = logging.getLogger(__name__)

# asyncpg uses postgresql:// not postgresql+asyncpg://
_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Guard against concurrent resume attempts for the same chat
_resuming: set[str] = set()


def _extract_text(content: str) -> str:
    """Extract plain text from structured content JSON.

    Handles text blocks, mention blocks (rendered as ``@name``), skill blocks
    (rendered as ``/name`` with a trailing annotation), and legacy plain-text
    content for backward compatibility.
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "blocks" in data:
            parts = []
            skill_names = []
            for block in data["blocks"]:
                if block.get("type") == "text":
                    parts.append(block["value"])
                elif block.get("type") == "mention":
                    parts.append(f"@{block['display_name']}")
                elif block.get("type") == "skill":
                    name = block["name"]
                    parts.append(f"/{name}")
                    skill_names.append(name)
            text = "".join(parts)
            for name in skill_names:
                text += f"\n/{name} is a skill."
            return text
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return content


async def _resolve_project(chat_id: str) -> str:
    """Derive project_name from chat_id via the DB chain: chat → room → project."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT p.name "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN projects p ON p.id = r.project_id "
            "WHERE c.id = $1",
            uuid.UUID(chat_id),
        )
        if not row:
            raise ValueError(f"No project found for chat {chat_id}")
        return row["name"]
    finally:
        await conn.close()


async def _load_orchestrator(chat_id: str) -> dict:
    """Look up the coordinator for the project that owns this chat.

    Joins chat → room → project → project_members to find the member
    with type='coordinator'. Returns {id, display_name, project_id}.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT pm.id, pm.display_name, r.project_id "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN project_members pm ON pm.project_id = r.project_id "
            "WHERE c.id = $1 AND pm.type = 'coordinator'",
            uuid.UUID(chat_id),
        )
        if not row:
            raise ValueError(f"No coordinator member found for chat {chat_id}")
        return {
            "id": str(row["id"]),
            "display_name": row["display_name"],
            "project_id": str(row["project_id"]),
        }
    finally:
        await conn.close()


async def _load_chat_history(chat_id: str) -> list[dict]:
    """Load the full message history for a chat, ordered chronologically."""
    conn = await asyncpg.connect(_dsn)
    try:
        rows = await conn.fetch(
            "SELECT pm.display_name, m.content "
            "FROM messages m JOIN project_members pm ON pm.id = m.member_id "
            "WHERE m.chat_id = $1 ORDER BY m.created_at",
            uuid.UUID(chat_id),
        )
        return [
            {"display_name": r["display_name"], "content": _extract_text(r["content"])}
            for r in rows
        ]
    finally:
        await conn.close()


async def _ensure_delegate_exists(project_name: str) -> None:
    """Guarantee at least one AI agent (type='ai') exists for delegation.

    If no non-coordinator AI members exist, generate a new agent on-the-fly
    so the coordinator always has someone to delegate workloads to.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM project_members pm "
            "JOIN projects p ON p.id = pm.project_id "
            "WHERE pm.type = 'ai' AND p.name = $1",
            project_name,
        )
        if count == 0:
            logger.info(
                "No delegate agents for project '%s', creating one", project_name
            )
            await generate_agent_profile(project_name)
    finally:
        await conn.close()


async def _get_agent_names(project_name: str) -> list[str]:
    """Return display names of all AI agents (type='ai') for a project."""
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


async def _resolve_member(
    conn: asyncpg.Connection,
    project_name: str,
    owner_name: str,
) -> uuid.UUID:
    """Resolve an agent name to a project_members.id.

    The owner name is guaranteed valid because the LLM response is constrained
    to a Literal of available agent names.
    """
    row = await conn.fetchrow(
        "SELECT pm.id FROM project_members pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.display_name = $1 AND p.name = $2 AND pm.type = 'ai'",
        owner_name,
        project_name,
    )
    if not row:
        raise ValueError(f"Agent '{owner_name}' not found in project '{project_name}'")
    return row["id"]


async def _get_clone_path(project_name: str) -> str:
    """Resolve the clone_path for a project by name."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchval(
            "SELECT clone_path FROM projects WHERE name = $1",
            project_name,
        )
        if not row:
            raise ValueError(f"No project found with name '{project_name}'")
        return row
    finally:
        await conn.close()


async def _persist_workloads(
    workloads: list,
    main_chat_id: str,
    project_name: str,
) -> list[dict]:
    """Persist workloads and their associated chats to the database.

    Returns a list of dicts with full workload data for session startup.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT c.room_id, r.project_id FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "WHERE c.id = $1",
            uuid.UUID(main_chat_id),
        )
        room_id = row["room_id"]
        project_id = str(row["project_id"])

        results = []
        for w in workloads:
            # Support both Pydantic models (legacy) and dicts (dispatch flow)
            owner = w["owner"] if isinstance(w, dict) else w.owner
            title = w["title"] if isinstance(w, dict) else w.title
            description = w["description"] if isinstance(w, dict) else w.description
            bg_context = (
                w.get("background_context")
                if isinstance(w, dict)
                else w.background_context
            )
            problem = (
                w.get("problem") if isinstance(w, dict) else getattr(w, "problem", None)
            )
            perm_mode = (
                w.get("permission_mode", "default")
                if isinstance(w, dict)
                else "default"
            )

            member_id = await _resolve_member(conn, project_name, owner)

            workload_id = uuid.uuid4()
            chat_id = uuid.uuid4()
            now = datetime.now(timezone.utc)

            await conn.execute(
                "INSERT INTO workloads "
                "(id, main_chat_id, member_id, title, description, permission_mode, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                workload_id,
                uuid.UUID(main_chat_id),
                member_id,
                title,
                description,
                perm_mode,
                now,
            )

            await conn.execute(
                "INSERT INTO chats "
                "(id, room_id, type, title, owner_id, workload_id, status, updated_at, created_at) "
                "VALUES ($1, $2, 'workload', $3, $4, $5, 'assigned', $6, $6)",
                chat_id,
                room_id,
                title,
                member_id,
                workload_id,
                now,
            )

            results.append(
                {
                    "id": str(workload_id),
                    "project_id": project_id,
                    "room_id": str(room_id),
                    "main_chat_id": main_chat_id,
                    "chat_id": str(chat_id),
                    "member_id": str(member_id),
                    "display_name": owner,
                    "title": title,
                    "description": description,
                    "background_context": bg_context,
                    "problem": problem,
                    "permission_mode": perm_mode,
                    "status": "assigned",
                    "worktree_branch": None,
                    "session_id": None,
                }
            )

        return results
    finally:
        await conn.close()


async def listen(redis_client: aioredis.Redis):
    """Subscribe to ai:respond and handle AI mention requests.

    Receives only {chat_id}. Derives everything else from the DB:
    project_name via chat → room → project, orchestrator via project_members.
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("ai:respond")
    logger.info("Subscribed to ai:respond")

    async for raw in pubsub.listen():
        if raw["type"] != "message":
            continue

        msg = json.loads(raw["data"])
        chat_id = msg["chat_id"]

        # Resolve project and orchestrator from DB
        project_name = await _resolve_project(chat_id)
        orchestrator = await _load_orchestrator(chat_id)

        logger.info(
            "AI respond request — %s (project: %s, chat: %s)",
            orchestrator["display_name"],
            project_name,
            chat_id[:8],
        )

        try:
            # Ensure at least one delegate agent exists before the coordinator runs
            try:
                await asyncio.wait_for(_ensure_delegate_exists(project_name), timeout=120)
            except asyncio.TimeoutError:
                logger.error("Timed out creating delegate agent for '%s'", project_name)
            except Exception:
                logger.exception("Failed to ensure delegate agent for '%s'", project_name)

            # Get agent names for the dynamic Literal constraint
            agent_names = await _get_agent_names(project_name)

            # Fetch full conversation history for context
            conversation = await _load_chat_history(chat_id)
            logger.info("Loaded %d messages from database", len(conversation))

            set_cost_context(
                member_id=orchestrator["id"],
                project_id=orchestrator["project_id"],
            )

            agent_response = await run_agent(
                conversation,
                project_name,
                agent_names,
                orchestrator["display_name"],
            )
            content = agent_response.response  # type: ignore[reportAttributeAccessIssue]
            logger.info("Agent returned %d chars", len(content))

            if agent_response.workloads:  # type: ignore[reportAttributeAccessIssue]
                dispatch_items = [
                    {
                        "owner": w.owner,
                        "title": w.title,
                        "description": w.description,
                        "background_context": w.background_context,
                        "problem": w.problem,
                    }
                    for w in agent_response.workloads  # type: ignore[reportAttributeAccessIssue]
                ]
                blocks = [
                    {"type": "text", "value": content},
                    {
                        "type": "dispatch_card",
                        "dispatch_id": str(uuid.uuid4()),
                        "chat_id": chat_id,
                        "workloads": dispatch_items,
                    },
                ]
                logger.info(
                    "Dispatch card with %d workloads: %s",
                    len(dispatch_items),
                    ", ".join(f"{w['owner']}: {w['title']}" for w in dispatch_items),
                )
            else:
                blocks = [{"type": "text", "value": content}]

            # Wrap response in structured format for consistency
            structured_content = json.dumps(
                {
                    "blocks": blocks,
                    "mentions": [],
                }
            )

            response = {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "member_id": orchestrator["id"],
                "display_name": orchestrator["display_name"],
                "type": "coordinator",
                "content": structured_content,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "reply_to_id": None,
            }

            await redis_client.publish("chat:responses", json.dumps(response))
            logger.info("Published response to chat:responses")
        except Exception:
            logger.exception("Error handling AI respond for chat %s", chat_id[:8])


async def _resume_and_deliver(
    chat_id: str,
    content: str,
    redis_client: aioredis.Redis,
) -> None:
    """Resume a session (workload or admin) and deliver the pending message."""
    _resuming.add(chat_id)
    try:
        # Try workload first
        workload_data = await fetch_workload_data_for_resume(chat_id)
        if workload_data:
            clone_path = workload_data.pop("clone_path")
            await start_workload_session(workload_data, clone_path, redis_client)
        else:
            # Try admin
            admin_data = await fetch_admin_chat_data(chat_id)
            if admin_data:
                await start_admin_session(admin_data, redis_client)
            else:
                logger.warning(
                    "Cannot resume chat %s — not found or no session_id", chat_id[:8]
                )
                return

        delivered = await route_message(chat_id, content)
        if delivered:
            logger.info("Resumed and delivered message to chat %s", chat_id[:8])
        else:
            logger.warning(
                "Resume succeeded but delivery failed for chat %s", chat_id[:8]
            )
    except Exception:
        logger.exception("Resume failed for chat %s", chat_id[:8])
    finally:
        _resuming.discard(chat_id)


async def _retry_route(
    chat_id: str, content: str, retries: int = 3, delay: float = 2.0
) -> None:
    """Retry routing a message to a session that is being resumed."""
    for attempt in range(retries):
        await asyncio.sleep(delay)
        delivered = await route_message(chat_id, content)
        if delivered:
            logger.info(
                "Retry-routed message to chat %s (attempt %d)", chat_id[:8], attempt + 1
            )
            return
    logger.warning(
        "Failed to route message to chat %s after %d retries", chat_id[:8], retries
    )


async def listen_chat_messages(redis_client: aioredis.Redis):
    """Subscribe to chat:messages and route to active workload or admin sessions."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("chat:messages")
    logger.info("Subscribed to chat:messages")

    async for raw in pubsub.listen():
        if raw["type"] != "message":
            continue

        msg = json.loads(raw["data"])
        chat_id = msg["chat_id"]
        content = msg["content"]

        delivered = await route_message(chat_id, content)
        if delivered:
            logger.info("Routed follow-up to chat %s", chat_id[:8])
            continue

        # No active session — attempt to resume
        if chat_id in _resuming:
            logger.info("Resume in progress for chat %s, scheduling retry", chat_id[:8])
            asyncio.create_task(
                _retry_route(chat_id, content),
                name=f"chat-retry-{chat_id[:8]}",
            )
            continue

        logger.info("No active session for chat %s, starting resume", chat_id[:8])
        asyncio.create_task(
            _resume_and_deliver(chat_id, content, redis_client),
            name=f"chat-resume-{chat_id[:8]}",
        )


async def listen_tool_approvals(redis_client: aioredis.Redis):
    """Subscribe to tool:approvals and resolve pending approval Futures."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("tool:approvals")
    logger.info("Subscribed to tool:approvals")

    async for raw in pubsub.listen():
        if raw["type"] != "message":
            continue

        msg = json.loads(raw["data"])
        session_key = msg["chat_id"]
        approval_request_id = msg["approval_request_id"]
        decision = {
            "decision": msg["decision"],
            "tool_name": msg.get("tool_name"),
            "reason": msg.get("reason"),
        }

        resolved = resolve_tool_approval(session_key, approval_request_id, decision)
        if resolved:
            logger.info(
                "Resolved tool approval %s → %s (session %s)",
                approval_request_id[:8],
                msg["decision"],
                session_key[:8],
            )
        else:
            logger.warning(
                "Failed to resolve tool approval %s (session %s)",
                approval_request_id[:8],
                session_key[:8],
            )


async def listen_dispatch_confirmations(redis_client: aioredis.Redis):
    """Subscribe to dispatch:confirmed and start workload sessions.

    The API service publishes to this channel when a user confirms a dispatch
    card. Each message contains persisted workload data and the clone_path.
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("dispatch:confirmed")
    logger.info("Subscribed to dispatch:confirmed")

    async for raw in pubsub.listen():
        if raw["type"] != "message":
            continue

        msg = json.loads(raw["data"])
        clone_path = msg["clone_path"]
        workloads = msg["workloads"]

        logger.info(
            "Dispatch confirmed — starting %d workload(s)",
            len(workloads),
        )

        for wd in workloads:
            asyncio.create_task(
                start_workload_session(wd, clone_path, redis_client),
                name=f"workload-start-{wd['chat_id'][:8]}",
            )
