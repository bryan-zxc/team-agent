import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..guards import get_current_user
from ..models.chat import Chat
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.room import Room
from ..models.workload import Workload

logger = logging.getLogger(__name__)


def _get_redis():
    from ..main import redis_client
    return redis_client

router = APIRouter(dependencies=[Depends(get_current_user)])


class ToolApprovalRequest(BaseModel):
    approval_request_id: str
    decision: Literal["approve", "approve_session", "approve_project", "deny"]
    tool_name: str
    reason: str | None = None


class StatusUpdateRequest(BaseModel):
    status: Literal["completed"]


class DispatchWorkloadItem(BaseModel):
    owner: str
    title: str
    description: str
    background_context: str
    problem: str | None = None
    permission_mode: Literal["default", "acceptEdits"] = "default"


class DispatchRequest(BaseModel):
    chat_id: str
    dispatch_id: str
    workloads: list[DispatchWorkloadItem]


class SwitchModeRequest(BaseModel):
    permission_mode: Literal["default", "acceptEdits"]


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


@router.post("/workloads/dispatch", status_code=201)
async def dispatch_workloads(req: DispatchRequest):
    """Persist workloads from a dispatch card and trigger session startup."""
    clone_path = None
    results = []

    async with async_session() as session:
        # Resolve room and project from the main chat
        chat_result = await session.execute(
            select(Chat).where(Chat.id == uuid.UUID(req.chat_id))
        )
        chat = chat_result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        room_result = await session.execute(
            select(Room).where(Room.id == chat.room_id)
        )
        room = room_result.scalar_one_or_none()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        project_result = await session.execute(
            select(Project).where(Project.id == room.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        clone_path = project.clone_path

        for w in req.workloads:
            # Resolve member_id from agent display_name
            member_result = await session.execute(
                select(ProjectMember).where(
                    ProjectMember.display_name == w.owner,
                    ProjectMember.project_id == project.id,
                    ProjectMember.type == "ai",
                )
            )
            member = member_result.scalar_one_or_none()
            if not member:
                raise HTTPException(
                    status_code=422, detail=f"Agent '{w.owner}' not found",
                )

            workload_id = uuid.uuid4()
            chat_id = uuid.uuid4()
            now = datetime.now(timezone.utc)

            workload = Workload(
                id=workload_id,
                main_chat_id=uuid.UUID(req.chat_id),
                member_id=member.id,
                title=w.title,
                description=w.description,
                status="assigned",
                permission_mode=w.permission_mode,
                updated_at=now,
            )
            session.add(workload)
            await session.flush()  # ensure workload FK exists before chat insert

            workload_chat = Chat(
                id=chat_id,
                room_id=room.id,
                type="workload",
                title=w.title,
                owner_id=member.id,
                workload_id=workload_id,
            )
            session.add(workload_chat)

            results.append({
                "id": str(workload_id),
                "project_id": str(project.id),
                "room_id": str(room.id),
                "main_chat_id": req.chat_id,
                "chat_id": str(chat_id),
                "member_id": str(member.id),
                "display_name": w.owner,
                "title": w.title,
                "description": w.description,
                "background_context": w.background_context,
                "problem": w.problem,
                "permission_mode": w.permission_mode,
                "status": "assigned",
                "worktree_branch": None,
                "session_id": None,
            })

        await session.commit()

    # Publish to Redis so AI service starts sessions
    await _get_redis().publish(
        "dispatch:confirmed",
        json.dumps({"clone_path": clone_path, "workloads": results}),
    )

    logger.info(
        "Dispatched %d workload(s) for chat %s",
        len(results), req.chat_id[:8],
    )

    return {"workloads": [{"id": r["id"], "title": r["title"]} for r in results]}


@router.post("/workloads/{workload_id}/switch-mode")
async def switch_workload_mode(workload_id: str, req: SwitchModeRequest):
    """Switch a workload's permission mode — interrupt, update DB, auto-resume."""
    room_id = None
    updated_at = None

    async with async_session() as session:
        result = await session.execute(
            select(Workload).where(Workload.id == uuid.UUID(workload_id))
        )
        workload = result.scalar_one_or_none()
        if not workload:
            raise HTTPException(status_code=404, detail="Workload not found")

        if workload.permission_mode == req.permission_mode:
            return {"status": "no_change"}

        # 1. Interrupt if running
        if workload.status == "running":
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{settings.ai_service_url}/workloads/{workload_id}/interrupt",
                )
                if resp.status_code >= 400 and resp.status_code != 404:
                    raise HTTPException(
                        status_code=resp.status_code, detail=resp.text,
                    )

        # 2. Update permission_mode
        workload.permission_mode = req.permission_mode
        workload.updated_at = datetime.now(timezone.utc)
        updated_at = workload.updated_at
        await session.commit()

    # 3. Look up room_id for status broadcast
    async with async_session() as session:
        chat_result = await session.execute(
            select(Chat.room_id).where(
                Chat.workload_id == uuid.UUID(workload_id)
            )
        )
        row = chat_result.first()
        if row:
            room_id = str(row[0])

    # 4. Broadcast mode change
    if room_id and updated_at:
        await _get_redis().publish(
            "workload:status",
            json.dumps({
                "workload_id": workload_id,
                "status": "needs_attention",
                "permission_mode": req.permission_mode,
                "room_id": room_id,
                "updated_at": updated_at.isoformat(),
            }),
        )

    # 5. Auto-resume with a system message
    mode_label = "vibe coding" if req.permission_mode == "acceptEdits" else "standard"
    await _get_redis().publish(
        "workload:messages",
        json.dumps({
            "workload_id": workload_id,
            "content": f"Session restarted with {mode_label} mode. Continue where you left off.",
        }),
    )

    logger.info(
        "Switched workload %s to %s mode",
        workload_id[:8], req.permission_mode,
    )

    return {"status": "switching", "permission_mode": req.permission_mode}
