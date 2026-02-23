import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings, setup_logging
from .database import async_session, engine
from .models.message import Message
from .routes.files import router as files_router
from .routes.members import router as members_router
from .routes.projects import router as projects_router
from .routes.rooms import router as rooms_router
from .routes.users import router as users_router
from .routes.workloads import router as workloads_router
from .websocket.handler import router as ws_router
from .websocket.manager import manager

setup_logging()
logger = logging.getLogger(__name__)

redis_client = aioredis.from_url(settings.redis_url)


async def _listen_for_workload_status():
    """Subscribe to workload:status and broadcast to room WebSocket clients."""
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    await pubsub.subscribe("workload:status")
    logger.info("Subscribed to workload:status")

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            event = json.loads(raw["data"])
            room_id = event.get("room_id")
            if not room_id:
                continue

            # Wrap with _event marker so frontend can distinguish from chat messages
            event["_event"] = "workload_status"
            await manager.broadcast_room(uuid.UUID(room_id), event)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("workload:status")
        await sub_client.aclose()


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
                member_id=uuid.UUID(msg_data["member_id"]),
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
    ai_task = asyncio.create_task(_listen_for_ai_responses())
    status_task = asyncio.create_task(_listen_for_workload_status())
    yield
    ai_task.cancel()
    status_task.cancel()
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="Team Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(members_router)
app.include_router(rooms_router)
app.include_router(users_router)
app.include_router(files_router)
app.include_router(workloads_router)
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
