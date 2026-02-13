from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from src.api.config import settings

engine = create_async_engine(settings.database_url)
redis_client = aioredis.from_url(settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="Team Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
