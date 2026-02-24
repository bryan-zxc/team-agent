import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agents import generate_agent_profile
from .config import settings, setup_logging
from .cost import init_cost_tracker
from .listener import listen, listen_tool_approvals, listen_workload_messages
from .workload import shutdown_all_sessions, stop_workload_session

setup_logging()
logger = logging.getLogger(__name__)


class GenerateAgentRequest(BaseModel):
    project_name: str
    name: Optional[str] = None
    member_type: str = "ai"


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = aioredis.from_url(settings.redis_url)

    try:
        await client.ping()
        logger.info("AI service connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    app.state.redis = client
    init_cost_tracker(client)

    listener_task = asyncio.create_task(listen(client))
    workload_listener_task = asyncio.create_task(listen_workload_messages(client))
    tool_approval_task = asyncio.create_task(listen_tool_approvals(client))

    yield

    await shutdown_all_sessions()
    listener_task.cancel()
    workload_listener_task.cancel()
    tool_approval_task.cancel()
    await client.aclose()
    logger.info("AI service shut down")


app = FastAPI(title="AI Service", lifespan=lifespan)


@app.post("/workloads/{workload_id}/interrupt")
async def interrupt_workload(workload_id: str):
    """Interrupt a running workload — transitions to needs_attention."""
    found = await stop_workload_session(workload_id, "needs_attention", app.state.redis)
    if not found:
        raise HTTPException(status_code=404, detail="Workload not found")
    return {"status": "interrupted"}


@app.post("/workloads/{workload_id}/cancel")
async def cancel_workload(workload_id: str):
    """Cancel a workload — transitions to cancelled."""
    found = await stop_workload_session(workload_id, "cancelled", app.state.redis)
    if not found:
        raise HTTPException(status_code=404, detail="Workload not found")
    return {"status": "cancelled"}


@app.post("/generate-agent")
async def generate_agent(req: GenerateAgentRequest):
    """Generate an AI agent profile via LLM."""
    try:
        result = await generate_agent_profile(req.project_name, name=req.name, member_type=req.member_type)
    except Exception as e:
        logger.error("Agent creation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": result["id"],
        "display_name": result["display_name"],
        "type": "ai",
    }
