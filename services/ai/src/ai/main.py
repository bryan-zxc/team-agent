import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .agents import generate_agent_profile
from .config import memory_handler, settings, setup_logging
from .cost import init_cost_tracker, set_cost_context
from .llm import llm
from .admin import shutdown_all_admin_sessions
from .listener import (
    listen,
    listen_chat_messages,
    listen_dispatch_confirmations,
    listen_tool_approvals,
)
from .screencast import shutdown_all_screencasts
from .session import (
    get_coordinator_for_chat,
    publish_message,
    publish_status_event,
    stop_session,
    update_chat_status,
)
from .terminal import (
    create_terminal_session,
    destroy_terminal_session,
    shutdown_all_terminal_sessions,
)
from .workload import (
    fetch_workload_data_for_retry,
    start_workload_session,
    shutdown_all_workload_sessions,
)
from .terminal_listener import listen_terminal_input

setup_logging()
logger = logging.getLogger(__name__)


class GenerateAgentRequest(BaseModel):
    project_name: str
    name: Optional[str] = None
    member_type: str = "ai"


class CreateTerminalRequest(BaseModel):
    cwd: str


class ResolveRequest(BaseModel):
    outcome: Literal["success", "failed"]
    message: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = aioredis.from_url(settings.redis_url)

    try:
        await client.ping()  # type: ignore[reportGeneralTypeIssues]
        logger.info("AI service connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    app.state.redis = client
    init_cost_tracker(client)

    listener_task = asyncio.create_task(listen(client))
    chat_listener_task = asyncio.create_task(listen_chat_messages(client))
    tool_approval_task = asyncio.create_task(listen_tool_approvals(client))
    dispatch_task = asyncio.create_task(listen_dispatch_confirmations(client))
    terminal_input_task = asyncio.create_task(listen_terminal_input(client))

    yield

    await shutdown_all_workload_sessions(client)
    await shutdown_all_admin_sessions(client)
    await shutdown_all_screencasts()
    await shutdown_all_terminal_sessions()
    listener_task.cancel()
    chat_listener_task.cancel()
    tool_approval_task.cancel()
    dispatch_task.cancel()
    terminal_input_task.cancel()
    await client.aclose()
    logger.info("AI service shut down")


app = FastAPI(title="AI Service", lifespan=lifespan)


@app.post("/chats/{chat_id}/interrupt")
async def interrupt_session(chat_id: str):
    """Interrupt a running session — transitions to needs_attention."""
    found = await stop_session(chat_id, "needs_attention", app.state.redis)
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "interrupted"}


@app.post("/chats/{chat_id}/cancel")
async def cancel_session(chat_id: str):
    """Cancel a session — transitions to cancelled, purges worktree."""
    found = await stop_session(chat_id, "cancelled", app.state.redis, purge=True)
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")
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


@app.get("/diagnostics/logs")
async def get_logs(
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    since: Optional[datetime] = Query(None),
):
    """Return recent application logs from the in-memory ring buffer."""
    return memory_handler.get_records(level=level, limit=limit, since=since)


@app.post("/generate-agent")
async def generate_agent(req: GenerateAgentRequest):
    """Generate an AI agent profile via LLM."""
    try:
        result = await generate_agent_profile(
            req.project_name, name=req.name, member_type=req.member_type
        )
    except Exception as e:
        logger.error("Agent creation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": result["id"],
        "display_name": result["display_name"],
        "type": "ai",
        "avatar": result.get("avatar"),
    }


class SummariseRequest(BaseModel):
    text: str
    context: str
    member_id: str
    project_id: str


_SUMMARISE_SYSTEM = (
    "You are summarising project activity for a daily standup report. "
    "Given a dialogue transcript from a one-hour window of a project chat, "
    "write a detailed summary of what happened. "
    "Give full attention to human instructions, decisions, and conversation — "
    "capture what they asked for, what they decided, and what guidance they gave. "
    "Condense tool approval actions (allow/deny) into a single line. "
    "Focus on outcomes, direction, and context — not mechanical details."
)


@app.post("/summarise")
async def summarise(req: SummariseRequest):
    """Summarise a chunk of chat dialogue using LLM."""
    set_cost_context(member_id=req.member_id, project_id=req.project_id)
    try:
        result = await llm.a_get_response(
            messages=[{"role": "user", "content": req.text}],
            system_instruction=_SUMMARISE_SYSTEM,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("Summarise failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    text = result.output_text if hasattr(result, "output_text") else str(result)  # type: ignore[reportAttributeAccessIssue]
    return {"summary": text}


@app.post("/terminals")
async def create_terminal(req: CreateTerminalRequest):
    """Create a terminal session with a PTY."""
    session_id = await create_terminal_session(
        cwd=req.cwd, redis_client=app.state.redis
    )
    return {"session_id": session_id}


@app.delete("/terminals/{session_id}")
async def delete_terminal(session_id: str):
    """Destroy a terminal session."""
    found = await destroy_terminal_session(session_id)
    if not found:
        raise HTTPException(status_code=404, detail="Terminal session not found")
    return {"status": "destroyed"}


@app.post("/chats/{chat_id}/resolve")
async def resolve_workload(chat_id: str, req: ResolveRequest):
    """Admin session resolved an escalated issue — transition workload back."""
    redis = app.state.redis

    data = await fetch_workload_data_for_retry(chat_id)
    if not data:
        raise HTTPException(status_code=404, detail="Workload chat not found")

    room_id = data.get("room_id", "")

    await update_chat_status(chat_id, "needs_attention")
    await publish_status_event(
        redis, chat_id, "needs_attention", room_id, chat_type="workload"
    )

    try:
        coordinator = await get_coordinator_for_chat(chat_id)
        main_chat_id = data.get("main_chat_id")

        if main_chat_id:
            if req.outcome == "success":
                text = (
                    req.message
                    or "I've resolved the issue. The workload is ready for review."
                )
            else:
                text = (
                    req.message
                    or "I wasn't able to resolve the issue automatically. Manual intervention needed."
                )

            await publish_message(
                redis,
                main_chat_id,
                coordinator["id"],
                coordinator["display_name"],
                "coordinator",
                [{"type": "text", "value": text}],
            )
    except Exception:
        logger.warning("Failed to post coordinator message for resolve", exc_info=True)

    return {"status": "needs_attention", "outcome": req.outcome}


@app.post("/chats/{chat_id}/retry")
async def retry_workload(chat_id: str):
    """Admin session requests a fresh retry of a failed workload session."""
    redis = app.state.redis

    data = await fetch_workload_data_for_retry(chat_id)
    if not data:
        raise HTTPException(status_code=404, detail="Workload chat not found")

    clone_path = data["clone_path"]

    try:
        await start_workload_session(data, clone_path, redis)
    except Exception as e:
        logger.error("Retry failed for chat %s: %s", chat_id[:8], e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "retrying"}
