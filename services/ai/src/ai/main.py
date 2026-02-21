import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agents import generate_agent_profile
from .config import settings, setup_logging
from .cost.models import Base
from .database import engine
from .listener import listen

setup_logging()
logger = logging.getLogger(__name__)


class GenerateAgentRequest(BaseModel):
    project_name: str
    name: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create cost tracking table if it doesn't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    client = aioredis.from_url(settings.redis_url)

    try:
        await client.ping()
        logger.info("AI service connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    listener_task = asyncio.create_task(listen(client))

    yield

    listener_task.cancel()
    await client.aclose()
    await engine.dispose()
    logger.info("AI service shut down")


app = FastAPI(title="AI Service", lifespan=lifespan)


@app.post("/generate-agent")
async def generate_agent(req: GenerateAgentRequest):
    """Generate an AI agent profile via LLM."""
    try:
        result = await generate_agent_profile(req.project_name, name=req.name)
    except Exception as e:
        logger.error("Agent creation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": result["id"],
        "display_name": result["display_name"],
        "type": "ai",
    }
