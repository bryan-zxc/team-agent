"""Redis listener for terminal input — routes keystrokes and resize events to PTY sessions."""

import asyncio
import base64
import json
import logging

import redis.asyncio as aioredis

from .terminal import resize_terminal, write_terminal_input

logger = logging.getLogger(__name__)


async def listen_terminal_input(redis_client: aioredis.Redis) -> None:
    """Subscribe to terminal:input and route messages to the appropriate PTY."""
    from .config import settings

    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    await pubsub.subscribe("terminal:input")
    logger.info("Subscribed to terminal:input")

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue

            try:
                msg = json.loads(raw["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            session_id = msg.get("session_id")
            if not session_id:
                continue

            msg_type = msg.get("type")

            if msg_type == "input":
                data = base64.b64decode(msg.get("data", ""))
                write_terminal_input(session_id, data)

            elif msg_type == "resize":
                cols = msg.get("cols", 80)
                rows = msg.get("rows", 24)
                resize_terminal(session_id, cols, rows)

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("terminal:input")
        await sub_client.aclose()
