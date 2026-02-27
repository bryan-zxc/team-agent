"""WebSocket endpoint for terminal I/O relay via Redis pub/sub."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import settings
from ..database import async_session
from ..models.session import Session

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_redis():
    from ..main import redis_client
    return redis_client


@router.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    """Bidirectional relay between browser xterm.js and AI service PTY via Redis."""

    # Validate session cookie (same pattern as chat WebSocket)
    auth_session_id = websocket.cookies.get("session_id")
    if not auth_session_id:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    async with async_session() as db:
        auth_session = await db.get(Session, auth_session_id)
        if not auth_session or auth_session.expires_at < datetime.now(timezone.utc):
            await websocket.close(code=4001, reason="Invalid or expired session")
            return

    await websocket.accept()

    # Per-connection Redis subscriber for this terminal session's output
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    output_channel = f"terminal:output:{session_id}"
    await pubsub.subscribe(output_channel)

    async def relay_output():
        """Read from Redis terminal:output:{session_id} → send to WebSocket."""
        try:
            async for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue
                msg = json.loads(raw["data"])
                await websocket.send_json(msg)

                # If the PTY closed, notify and stop
                if msg.get("type") == "closed":
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Terminal output relay error for session %s", session_id[:8])

    async def relay_input():
        """Read from WebSocket → publish to Redis terminal:input."""
        redis = _get_redis()
        try:
            while True:
                data = await websocket.receive_json()
                # Attach session_id and forward to AI service
                data["session_id"] = session_id
                await redis.publish("terminal:input", json.dumps(data))
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Terminal input relay error for session %s", session_id[:8])

    # Run both relays concurrently — when either stops, cancel the other
    output_task = asyncio.create_task(relay_output())
    input_task = asyncio.create_task(relay_input())

    try:
        done, pending = await asyncio.wait(
            [output_task, input_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        await pubsub.unsubscribe(output_channel)
        await sub_client.aclose()
        logger.info("Terminal WebSocket closed for session %s", session_id[:8])
