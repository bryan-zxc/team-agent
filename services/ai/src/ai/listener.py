import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from .agents import generate_agent_profile
from .config import settings
from .runner import run_agent

logger = logging.getLogger(__name__)

# asyncpg uses postgresql:// not postgresql+asyncpg://
_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _extract_text(content: str) -> str:
    """Extract plain text from structured content JSON.

    Handles both structured ``{"blocks": [...], "mentions": [...]}`` and
    legacy plain-text content for backward compatibility.
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "blocks" in data:
            return " ".join(
                block["value"]
                for block in data["blocks"]
                if block.get("type") == "text"
            )
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
    with type='coordinator'. Returns {id, display_name}.
    """
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
            raise ValueError(f"No coordinator member found for chat {chat_id}")
        return {"id": str(row["id"]), "display_name": row["display_name"]}
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
            logger.info("No delegate agents for project '%s', creating one", project_name)
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
    conn: asyncpg.Connection, project_name: str, owner_name: str,
) -> uuid.UUID:
    """Resolve an agent name to a project_members.id.

    The owner name is guaranteed valid because the LLM response is constrained
    to a Literal of available agent names.
    """
    row = await conn.fetchrow(
        "SELECT pm.id FROM project_members pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.display_name = $1 AND p.name = $2 AND pm.type = 'ai'",
        owner_name, project_name,
    )
    if not row:
        raise ValueError(f"Agent '{owner_name}' not found in project '{project_name}'")
    return row["id"]


async def _persist_workloads(
    workloads: list,
    main_chat_id: str,
    project_name: str,
) -> list[dict]:
    """Persist workloads and their associated chats to the database.

    Returns a list of dicts with {owner_name, title} for response enrichment.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        room_id = await conn.fetchval(
            "SELECT room_id FROM chats WHERE id = $1",
            uuid.UUID(main_chat_id),
        )

        results = []
        for w in workloads:
            member_id = await _resolve_member(conn, project_name, w.owner)

            workload_id = uuid.uuid4()
            chat_id = uuid.uuid4()
            now = datetime.now(timezone.utc)

            await conn.execute(
                "INSERT INTO workloads "
                "(id, main_chat_id, member_id, title, description, status, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5, 'assigned', $6, $6)",
                workload_id, uuid.UUID(main_chat_id), member_id,
                w.title, w.description, now,
            )

            await conn.execute(
                "INSERT INTO chats "
                "(id, room_id, type, title, owner_id, workload_id, created_at) "
                "VALUES ($1, $2, 'workload', $3, $4, $5, $6)",
                chat_id, room_id, w.title, member_id, workload_id, now,
            )

            results.append({"owner_name": w.owner, "title": w.title})

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

        # Ensure at least one delegate agent exists before the coordinator runs
        await _ensure_delegate_exists(project_name)

        # Get agent names for the dynamic Literal constraint
        agent_names = await _get_agent_names(project_name)

        # Fetch full conversation history for context
        conversation = await _load_chat_history(chat_id)
        logger.info("Loaded %d messages from database", len(conversation))

        agent_response = await run_agent(
            conversation, project_name, agent_names, orchestrator["display_name"],
        )
        content = agent_response.response
        logger.info("Agent returned %d chars", len(content))

        if agent_response.workloads:
            persisted = await _persist_workloads(
                agent_response.workloads, chat_id, project_name,
            )
            logger.info(
                "Persisted %d workloads: %s",
                len(persisted),
                ", ".join(f"{w['owner_name']}: {w['title']}" for w in persisted),
            )
            assignment_lines = [
                f"- {w['owner_name']}: {w['title']}" for w in persisted
            ]
            content += "\n\nWorkloads assigned:\n" + "\n".join(assignment_lines)

        # Wrap response in structured format for consistency
        structured_content = json.dumps({
            "blocks": [{"type": "text", "value": content}],
            "mentions": [],
        })

        response = {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "member_id": orchestrator["id"],
            "display_name": orchestrator["display_name"],
            "type": "coordinator",
            "content": structured_content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await redis_client.publish("chat:responses", json.dumps(response))
        logger.info("Published response to chat:responses")
