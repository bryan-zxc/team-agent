import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm.attributes import flag_modified

from ..config import settings
from ..database import async_session
from ..guards import get_current_user, get_unlocked_project
from ..models.activity_heartbeat import ActivityHeartbeat
from ..models.llm_usage import LLMUsage
from ..models.project import Project
from ..models.project_member import ProjectMember
from ..models.timesheet import Timesheet
from ..models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class AddHumanRequest(BaseModel):
    user_id: str


class GenerateAgentRequest(BaseModel):
    name: str | None = None


class UpdateProfileRequest(BaseModel):
    content: str


def _profile_path(clone_path: str, display_name: str) -> Path:
    """Compute the markdown profile path for an AI member."""
    return Path(clone_path) / ".team-agent" / "agents" / f"{display_name.lower()}.md"


@router.get("/projects/{project_id}/members")
async def list_members(project_id: uuid.UUID):
    async with async_session() as session:
        members = (
            (
                await session.execute(
                    select(ProjectMember)
                    .where(ProjectMember.project_id == project_id)
                    .order_by(ProjectMember.created_at)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": str(m.id),
                "display_name": m.display_name,
                "type": m.type,
                "user_id": str(m.user_id) if m.user_id else None,
                "avatar": m.avatar,
                "settings": m.settings or {},
            }
            for m in members
        ]


@router.get("/projects/{project_id}/available-users")
async def available_users(project_id: uuid.UUID):
    """Users not yet added as members of this project."""
    async with async_session() as session:
        existing_user_ids = (
            (
                await session.execute(
                    select(ProjectMember.user_id).where(
                        ProjectMember.project_id == project_id,
                        ProjectMember.user_id.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        query = select(User).order_by(User.display_name)
        if existing_user_ids:
            query = query.where(User.id.notin_(existing_user_ids))

        users = (await session.execute(query)).scalars().all()
        return [{"id": str(u.id), "display_name": u.display_name} for u in users]


@router.post("/projects/{project_id}/members/human")
async def add_human_member(
    req: AddHumanRequest,
    project: Project = Depends(get_unlocked_project),
):
    async with async_session() as session:
        user = await session.get(User, uuid.UUID(req.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            display_name=user.display_name,
            type="human",
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        return {
            "id": str(member.id),
            "display_name": member.display_name,
            "type": member.type,
            "avatar": member.avatar,
        }


@router.post("/projects/{project_id}/members/ai")
async def generate_ai_member(
    req: GenerateAgentRequest,
    project: Project = Depends(get_unlocked_project),
):
    """Request AI agent generation via the AI service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.ai_service_url}/generate-agent",
                json={
                    "project_name": project.name,
                    "name": req.name,
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Agent generation timed out")
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail="AI service unavailable")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.json().get("detail", "Agent generation failed"),
        )

    return resp.json()


@router.get("/projects/{project_id}/members/{member_id}/profile")
async def get_profile(project_id: uuid.UUID, member_id: uuid.UUID):
    """Read the raw markdown profile for an AI member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

        project = await session.get(Project, project_id)
        if not project or not project.clone_path:
            raise HTTPException(status_code=404, detail="Project has no cloned repo")

    path = _profile_path(project.clone_path, member.display_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile file not found")

    return {"content": path.read_text()}


@router.put("/projects/{project_id}/members/{member_id}/profile")
async def update_profile(
    member_id: uuid.UUID,
    req: UpdateProfileRequest,
    project: Project = Depends(get_unlocked_project),
):
    """Write raw markdown back to the profile file."""
    if not project.clone_path:
        raise HTTPException(status_code=404, detail="Project has no cloned repo")

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project.id:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type == "human":
            raise HTTPException(status_code=400, detail="Only AI members have profiles")

    path = _profile_path(project.clone_path, member.display_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content)

    return {"status": "ok"}


@router.get("/projects/{project_id}/members/{member_id}/costs")
async def get_member_costs(project_id: uuid.UUID, member_id: uuid.UUID):
    """Return aggregated cost data for a member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(LLMUsage.cost), 0.0).label("total_cost"),
                    func.coalesce(
                        func.sum(
                            func.coalesce(LLMUsage.input_tokens, 0)
                            + func.coalesce(LLMUsage.output_tokens, 0)
                        ),
                        0,
                    ).label("total_tokens"),
                ).where(
                    LLMUsage.member_id == member_id,
                    LLMUsage.project_id == project_id,
                )
            )
        ).one()

        total_cost = float(row.total_cost)
        total_tokens = int(row.total_tokens)
        margin = member.margin_percent
        nsr = total_cost * (1 + margin / 100)

        return {
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "margin_percent": margin,
            "nsr": round(nsr, 2),
        }


class UpdateMarginRequest(BaseModel):
    margin_percent: float


@router.put("/projects/{project_id}/members/{member_id}/margin")
async def update_margin(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    req: UpdateMarginRequest,
):
    """Update the charge-out margin for a member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        current = dict(member.settings or {})
        current["margin_percent"] = req.margin_percent
        member.settings = current
        flag_modified(member, "settings")
        await session.commit()

        return {"margin_percent": member.margin_percent}


@router.post("/projects/{project_id}/members/{member_id}/heartbeat")
async def record_heartbeat(project_id: uuid.UUID, member_id: uuid.UUID):
    """Record one minute of active time for a human member."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")
        if member.type != "human":
            raise HTTPException(status_code=400, detail="Only human members track active time")

        stmt = (
            pg_insert(ActivityHeartbeat)
            .values(
                id=uuid.uuid4(),
                member_id=member_id,
                project_id=project_id,
                recorded_at=now,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()

    return {"status": "ok"}


@router.get("/projects/{project_id}/members/{member_id}/active-time")
async def get_active_time(project_id: uuid.UUID, member_id: uuid.UUID):
    """Return aggregated active time for a member."""
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        row = (
            await session.execute(
                select(
                    func.count()
                    .filter(ActivityHeartbeat.recorded_at >= start_of_today)
                    .label("today_minutes"),
                    func.count()
                    .filter(ActivityHeartbeat.recorded_at >= start_of_week)
                    .label("week_minutes"),
                    func.count().label("lifetime_minutes"),
                ).where(
                    ActivityHeartbeat.member_id == member_id,
                    ActivityHeartbeat.project_id == project_id,
                )
            )
        ).one()

        return {
            "today_minutes": row.today_minutes,
            "week_minutes": row.week_minutes,
            "lifetime_minutes": row.lifetime_minutes,
        }


@router.get("/projects/{project_id}/members/{member_id}/heartbeat-daily")
async def heartbeat_daily(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    start: str = Query(...),
    end: str = Query(...),
):
    """Return daily minute counts from heartbeats for a date range."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        rows = (
            await session.execute(
                select(
                    func.date(ActivityHeartbeat.recorded_at).label("day"),
                    func.count().label("minutes"),
                )
                .where(
                    ActivityHeartbeat.member_id == member_id,
                    ActivityHeartbeat.project_id == project_id,
                    func.date(ActivityHeartbeat.recorded_at) >= start_date,
                    func.date(ActivityHeartbeat.recorded_at) <= end_date,
                )
                .group_by(func.date(ActivityHeartbeat.recorded_at))
                .order_by(func.date(ActivityHeartbeat.recorded_at))
            )
        ).all()

        return [{"date": str(row.day), "minutes": row.minutes} for row in rows]


@router.get("/projects/{project_id}/members/{member_id}/settings")
async def get_member_settings(project_id: uuid.UUID, member_id: uuid.UUID):
    """Return configurable settings for a member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        return {
            "settings": member.settings or {},
            "defaults": {"margin_percent": 30.0, "timesheet_markup": 30.0, "rate": 0.0},
        }


ALLOWED_SETTINGS = {"margin_percent", "timesheet_markup", "rate"}


class UpdateSettingsRequest(BaseModel):
    settings: dict


@router.put("/projects/{project_id}/members/{member_id}/settings")
async def update_member_settings(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    req: UpdateSettingsRequest,
):
    """Update configurable settings for a member."""
    invalid = set(req.settings.keys()) - ALLOWED_SETTINGS
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown settings: {invalid}")

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        current = dict(member.settings or {})
        current.update(req.settings)
        member.settings = current
        flag_modified(member, "settings")
        await session.commit()

        return {"settings": member.settings}


class TimesheetEntry(BaseModel):
    date: str
    hours: float


class TimesheetBulkRequest(BaseModel):
    entries: list[TimesheetEntry]


@router.post("/projects/{project_id}/members/{member_id}/timesheets")
async def upsert_timesheets(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    req: TimesheetBulkRequest,
):
    """Bulk upsert timesheet entries for a member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        for entry in req.entries:
            stmt = (
                pg_insert(Timesheet)
                .values(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    member_id=member_id,
                    date=date.fromisoformat(entry.date),
                    hours=entry.hours,
                )
                .on_conflict_do_update(
                    constraint="uq_timesheets_project_member_date",
                    set_={"hours": entry.hours},
                )
            )
            await session.execute(stmt)

        await session.commit()
        return {"status": "ok", "count": len(req.entries)}


@router.get("/projects/{project_id}/members/{member_id}/timesheets")
async def get_timesheets(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    start: str = Query(...),
    end: str = Query(...),
):
    """Return timesheet entries for a member in a date range."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        rows = (
            await session.execute(
                select(Timesheet)
                .where(
                    Timesheet.project_id == project_id,
                    Timesheet.member_id == member_id,
                    Timesheet.date >= start_date,
                    Timesheet.date <= end_date,
                )
                .order_by(Timesheet.date)
            )
        ).scalars().all()

        return [{"date": str(t.date), "hours": t.hours} for t in rows]


@router.get("/projects/{project_id}/members/{member_id}/human-costs")
async def get_human_costs(project_id: uuid.UUID, member_id: uuid.UUID):
    """Return aggregated cost data for a human member."""
    async with async_session() as session:
        member = await session.get(ProjectMember, member_id)
        if not member or member.project_id != project_id:
            raise HTTPException(status_code=404, detail="Member not found")

        hours_row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(Timesheet.hours), 0.0).label("total_hours"),
                ).where(
                    Timesheet.member_id == member_id,
                    Timesheet.project_id == project_id,
                )
            )
        ).one()

        activity_row = (
            await session.execute(
                select(func.count().label("total_minutes")).where(
                    ActivityHeartbeat.member_id == member_id,
                    ActivityHeartbeat.project_id == project_id,
                )
            )
        ).one()

        total_hours = float(hours_row.total_hours)
        total_activity_minutes = int(activity_row.total_minutes)
        rate = member.rate

        activity_hours = total_activity_minutes / 60
        if activity_hours > 0 and total_hours > 0:
            avg_markup = ((total_hours / activity_hours) - 1) * 100
        else:
            avg_markup = 0.0

        return {
            "rate": rate,
            "total_hours": round(total_hours, 1),
            "total_activity_minutes": total_activity_minutes,
            "avg_markup_percent": round(avg_markup, 1),
            "nsr": round(rate * total_hours, 2),
        }


@router.get("/projects/{project_id}/resourcing")
async def get_resourcing(project_id: uuid.UUID):
    """Return all members with daily actuals for the resourcing dashboard."""
    async with async_session() as session:
        members = (
            (
                await session.execute(
                    select(ProjectMember)
                    .where(ProjectMember.project_id == project_id)
                    .order_by(ProjectMember.created_at)
                )
            )
            .scalars()
            .all()
        )

        result = []
        for m in members:
            entry = {
                "id": str(m.id),
                "name": m.display_name,
                "type": m.type,
                "settings": m.settings or {},
            }

            if m.type == "human":
                # Timesheet hours by date
                ts_rows = (
                    await session.execute(
                        select(Timesheet.date, Timesheet.hours)
                        .where(
                            Timesheet.member_id == m.id,
                            Timesheet.project_id == project_id,
                        )
                        .order_by(Timesheet.date)
                    )
                ).all()
                entry["timesheets"] = [
                    {"date": str(r.date), "hours": r.hours} for r in ts_rows
                ]

                # Activity minutes by date
                act_rows = (
                    await session.execute(
                        select(
                            func.date(ActivityHeartbeat.recorded_at).label("day"),
                            func.count().label("minutes"),
                        )
                        .where(
                            ActivityHeartbeat.member_id == m.id,
                            ActivityHeartbeat.project_id == project_id,
                        )
                        .group_by(func.date(ActivityHeartbeat.recorded_at))
                        .order_by(func.date(ActivityHeartbeat.recorded_at))
                    )
                ).all()
                entry["activity"] = [
                    {"date": str(r.day), "minutes": r.minutes} for r in act_rows
                ]

            elif m.type in ("ai", "coordinator"):
                # LLM costs by date
                cost_rows = (
                    await session.execute(
                        select(
                            func.date(LLMUsage.created_at).label("day"),
                            func.sum(LLMUsage.cost).label("cost"),
                        )
                        .where(
                            LLMUsage.member_id == m.id,
                            LLMUsage.project_id == project_id,
                        )
                        .group_by(func.date(LLMUsage.created_at))
                        .order_by(func.date(LLMUsage.created_at))
                    )
                ).all()
                entry["costs"] = [
                    {"date": str(r.day), "cost": round(float(r.cost), 2)}
                    for r in cost_rows
                ]

            result.append(entry)

        return {"members": result}
