import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from src.ai.config import settings

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

        # Placeholder trigger: respond when message contains @ai
        if "@ai" not in msg["content"].lower():
            continue

        logger.info("Trigger detected — responding to @ai mention")

        response = {
            "id": str(uuid.uuid4()),
            "chat_id": msg["chat_id"],
            "user_id": ai_user["id"],
            "display_name": ai_user["display_name"],
            "content": f"I heard you! You said: \"{msg['content']}\"",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await redis_client.publish("chat:responses", json.dumps(response))
        logger.info("Published response to chat:responses")
