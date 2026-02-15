import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from src.ai.config import settings
from src.ai.runner import run_agent

logger = logging.getLogger("ai-service")

# asyncpg uses postgresql:// not postgresql+asyncpg://
_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _load_ai_user() -> dict | None:
    """Load the first AI user from the database."""
    conn = await asyncpg.connect(_dsn)
    try:
        row = await conn.fetchrow("SELECT id, display_name FROM users WHERE type = 'ai' LIMIT 1")
        if row:
            return {"id": str(row["id"]), "display_name": row["display_name"]}
        return None
    finally:
        await conn.close()


async def _load_chat_history(chat_id: str) -> list[dict]:
    """Load the full message history for a chat, ordered chronologically."""
    conn = await asyncpg.connect(_dsn)
    try:
        rows = await conn.fetch(
            "SELECT u.display_name, m.content "
            "FROM messages m JOIN users u ON u.id = m.user_id "
            "WHERE m.chat_id = $1 ORDER BY m.created_at",
            uuid.UUID(chat_id),
        )
        return [{"display_name": r["display_name"], "content": r["content"]} for r in rows]
    finally:
        await conn.close()


async def listen(redis_client: aioredis.Redis):
    """Subscribe to chat:messages and handle incoming messages."""
    ai_user = await _load_ai_user()
    if not ai_user:
        logger.error("No AI user found in database — cannot respond")
        return

    logger.info("Listener started as %s (id=%s)", ai_user["display_name"], ai_user["id"])

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("chat:messages")
    logger.info("Subscribed to chat:messages")

    async for raw in pubsub.listen():
        if raw["type"] != "message":
            continue

        msg = json.loads(raw["data"])
        logger.info("[%s] %s: %s", msg["chat_id"][:8], msg["display_name"], msg["content"])

        # Skip messages from AI users to avoid loops
        if msg["user_id"] == ai_user["id"]:
            continue

        # Trigger: respond when message contains @zimomo
        if "@zimomo" not in msg["content"].lower():
            continue

        logger.info("Trigger detected — responding to @zimomo mention")

        # Fetch full conversation history for context
        conversation = await _load_chat_history(msg["chat_id"])
        content = await run_agent(conversation)

        response = {
            "id": str(uuid.uuid4()),
            "chat_id": msg["chat_id"],
            "user_id": ai_user["id"],
            "display_name": ai_user["display_name"],
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await redis_client.publish("chat:responses", json.dumps(response))
        logger.info("Published response to chat:responses")
