import json
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
