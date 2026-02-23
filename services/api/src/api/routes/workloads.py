import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models.workload import Workload

logger = logging.getLogger(__name__)


def _get_redis():
    from ..main import redis_client
    return redis_client

router = APIRouter()


class ToolApprovalRequest(BaseModel):
    approval_request_id: str
    decision: Literal["approve", "approve_session", "approve_project", "deny"]
    tool_name: str
    reason: str | None = None


class StatusUpdateRequest(BaseModel):
    status: Literal["completed"]


@router.post("/workloads/{workload_id}/tool-approval", status_code=202)
async def submit_tool_approval(workload_id: str, req: ToolApprovalRequest):
    """Submit a human decision for a pending tool approval request."""
    if req.decision == "deny" and not req.reason:
        raise HTTPException(status_code=422, detail="Reason is required when denying.")

    payload = {
        "workload_id": workload_id,
        "approval_request_id": req.approval_request_id,
        "decision": req.decision,
        "tool_name": req.tool_name,
        "reason": req.reason,
    }

    await _get_redis().publish("tool:approvals", json.dumps(payload))
    logger.info(
        "Published tool approval %s → %s (workload %s)",
        req.approval_request_id[:8], req.decision, workload_id[:8],
    )

    return {"status": "accepted"}


@router.post("/workloads/{workload_id}/interrupt")
async def interrupt_workload(workload_id: str):
    """Interrupt a running workload — proxy to AI service."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(
            f"{settings.ai_service_url}/workloads/{workload_id}/interrupt",
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Workload not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/workloads/{workload_id}/cancel")
async def cancel_workload(workload_id: str):
    """Cancel a workload — proxy to AI service."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(
            f"{settings.ai_service_url}/workloads/{workload_id}/cancel",
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Workload not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.patch("/workloads/{workload_id}")
async def update_workload_status(workload_id: str, req: StatusUpdateRequest):
    """Manually transition a workload status (needs_attention → completed)."""
    async with async_session() as session:
        result = await session.execute(
            select(Workload).where(Workload.id == uuid.UUID(workload_id))
        )
        workload = result.scalar_one_or_none()

        if not workload:
            raise HTTPException(status_code=404, detail="Workload not found")

        if workload.status != "needs_attention":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition from '{workload.status}' to '{req.status}'",
            )

        workload.status = req.status
        workload.updated_at = datetime.now(timezone.utc)
        await session.commit()

    # Publish status change so WebSocket clients get instant feedback
    # Look up room_id via chat
    room_id = None
    async with async_session() as session:
        from ..models.chat import Chat
        chat_result = await session.execute(
            select(Chat.room_id).where(Chat.workload_id == uuid.UUID(workload_id))
        )
        row = chat_result.first()
        if row:
            room_id = str(row[0])

    if room_id:
        await _get_redis().publish(
            "workload:status",
            json.dumps({
                "workload_id": workload_id,
                "status": req.status,
                "room_id": room_id,
                "updated_at": workload.updated_at.isoformat(),
            }),
        )

    return {"status": req.status}
