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
from .listener import listen, listen_dispatch_confirmations, listen_tool_approvals, listen_workload_messages
from .screencast import shutdown_all_screencasts
from .terminal import create_terminal_session, destroy_terminal_session, shutdown_all_terminal_sessions
from .terminal_listener import listen_terminal_input
from .workload import shutdown_all_sessions, stop_workload_session

setup_logging()
logger = logging.getLogger(__name__)


class GenerateAgentRequest(BaseModel):
    project_name: str
    name: Optional[str] = None
    member_type: str = "ai"


class CreateTerminalRequest(BaseModel):
    cwd: str


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
    dispatch_task = asyncio.create_task(listen_dispatch_confirmations(client))
    terminal_input_task = asyncio.create_task(listen_terminal_input(client))

    yield

    await shutdown_all_sessions()
    await shutdown_all_screencasts()
    await shutdown_all_terminal_sessions()
    listener_task.cancel()
    workload_listener_task.cancel()
    tool_approval_task.cancel()
    dispatch_task.cancel()
    terminal_input_task.cancel()
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


@app.get("/health")
async def health():
    redis_status = "disconnected"

    try:
        await app.state.redis.ping()
        redis_status = "connected"
    except Exception:
        pass

    ok = redis_status == "connected"
    return {"status": "ok" if ok else "degraded", "redis": redis_status}


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


@app.post("/terminals")
async def create_terminal(req: CreateTerminalRequest):
    """Create a terminal session with a PTY."""
    session_id = await create_terminal_session(cwd=req.cwd, redis_client=app.state.redis)
    return {"session_id": session_id}


@app.delete("/terminals/{session_id}")
async def delete_terminal(session_id: str):
    """Destroy a terminal session."""
    found = await destroy_terminal_session(session_id)
    if not found:
        raise HTTPException(status_code=404, detail="Terminal session not found")
    return {"status": "destroyed"}
