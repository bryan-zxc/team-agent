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
from .models.llm_usage import LLMUsage
from .models.message import Message
from .routes.files import router as files_router
from .routes.members import router as members_router
from .routes.projects import router as projects_router
from .routes.rooms import router as rooms_router
from .routes.auth import router as auth_router
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

            # Ephemeral events (e.g. agent_activity) — broadcast without persisting
            if msg_data.get("_event"):
                chat_id = msg_data.get("chat_id")
                if chat_id:
                    await manager.broadcast(uuid.UUID(chat_id), msg_data)
                continue

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


async def _run_migrations() -> None:
    """Run Alembic migrations on startup."""
    logger.info("Running database migrations...")
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "alembic", "upgrade", "head",
        cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("Migration failed: %s", stderr.decode())
        raise RuntimeError(f"Database migration failed: {stderr.decode()}")
    logger.info("Migrations applied: %s", stdout.decode().strip())


async def _listen_for_cost_tracking():
    """Subscribe to cost:usage and persist LLM cost records."""
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    await pubsub.subscribe("cost:usage")
    logger.info("Subscribed to cost:usage")

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            data = json.loads(raw["data"])

            record = LLMUsage(
                model=data["model"],
                provider=data["provider"],
                input_tokens=data.get("input_tokens"),
                output_tokens=data.get("output_tokens"),
                cost=data["cost"],
                request_type=data["request_type"],
                caller=data["caller"],
                session_id=data.get("session_id"),
                num_turns=data.get("num_turns"),
                duration_ms=data.get("duration_ms"),
            )
            async with async_session() as session:
                session.add(record)
                await session.commit()
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("cost:usage")
        await sub_client.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _run_migrations()
    ai_task = asyncio.create_task(_listen_for_ai_responses())
    status_task = asyncio.create_task(_listen_for_workload_status())
    cost_task = asyncio.create_task(_listen_for_cost_tracking())
    yield
    ai_task.cancel()
    status_task.cancel()
    cost_task.cancel()
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="Team Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
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
