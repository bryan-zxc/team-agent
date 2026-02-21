import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

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
    """Look up the orchestrator (Zimomo) for the project that owns this chat.

    Joins chat → room → project → project_members to find the AI member
    named Zimomo. Returns {id, display_name}.
    """
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT pm.id, pm.display_name "
            "FROM chats c "
            "JOIN rooms r ON r.id = c.room_id "
            "JOIN project_members pm ON pm.project_id = r.project_id "
            "WHERE c.id = $1 AND pm.type = 'ai' AND pm.display_name = 'Zimomo'",
            uuid.UUID(chat_id),
        )
        if not row:
            raise ValueError(f"No Zimomo member found for chat {chat_id}")
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

        # Fetch full conversation history for context
        conversation = await _load_chat_history(chat_id)
        logger.info("Loaded %d messages from database", len(conversation))

        agent_response = await run_agent(conversation, project_name)
        content = agent_response.response
        logger.info("Agent returned %d chars", len(content))

        if agent_response.workloads:
            logger.info(
                "Workloads assigned: %s",
                ", ".join(f"{w.owner}: {w.title}" for w in agent_response.workloads),
            )

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
            "type": "ai",
            "content": structured_content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await redis_client.publish("chat:responses", json.dumps(response))
        logger.info("Published response to chat:responses")
