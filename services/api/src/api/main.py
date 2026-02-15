import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.config import settings
from src.api.database import async_session, engine
from src.api.models.message import Message
from src.api.routes.rooms import router as rooms_router
from src.api.routes.users import router as users_router
from src.api.websocket.handler import router as ws_router
from src.api.websocket.manager import manager

logger = logging.getLogger("api")

redis_client = aioredis.from_url(settings.redis_url)


async def _listen_for_ai_responses():
    """Subscribe to chat:responses and broadcast AI messages to WebSocket clients."""
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    await pubsub.subscribe("chat:responses")
    logger.info("Subscribed to chat:responses")

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            msg_data = json.loads(raw["data"])

            # Persist to PostgreSQL
            message = Message(
                id=uuid.UUID(msg_data["id"]),
                chat_id=uuid.UUID(msg_data["chat_id"]),
                user_id=uuid.UUID(msg_data["user_id"]),
                content=msg_data["content"],
            )
            async with async_session() as session:
                session.add(message)
                await session.commit()
                await session.refresh(message)

            # Broadcast to connected WebSocket clients
            await manager.broadcast(uuid.UUID(msg_data["chat_id"]), msg_data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("chat:responses")
        await sub_client.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_listen_for_ai_responses())
    yield
    task.cancel()
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="Team Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms_router)
app.include_router(users_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    pg_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        pg_status = "connected"
    except Exception:
        pass

    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception:
        pass

    return {
        "status": "ok" if pg_status == "connected" and redis_status == "connected" else "degraded",
        "postgres": pg_status,
        "redis": redis_status,
    }
