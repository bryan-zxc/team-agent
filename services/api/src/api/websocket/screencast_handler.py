"""WebSocket endpoint for screencast frame relay via Redis pub/sub."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket

from ..config import settings
from ..database import async_session
from ..models.session import Session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/screencast/{workload_id}")
async def screencast_websocket(websocket: WebSocket, workload_id: str):
    """One-way relay: Redis screencast:frames:{workload_id} → WebSocket."""

    # Validate session cookie (same pattern as terminal handler)
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

    # Per-connection Redis subscriber for this workload's screencast frames
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    channel = f"screencast:frames:{workload_id}"
    await pubsub.subscribe(channel)

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            msg = json.loads(raw["data"])
            await websocket.send_json(msg)

            # If the screencast stopped, notify and break
            if msg.get("type") == "stopped":
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Screencast relay error for workload %s", workload_id[:8])
    finally:
        await pubsub.unsubscribe(channel)
        await sub_client.aclose()
        logger.info("Screencast WebSocket closed for workload %s", workload_id[:8])
