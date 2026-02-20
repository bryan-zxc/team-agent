from fastapi import APIRouter
from sqlalchemy import select

from ..database import async_session
from ..models.project_member import ProjectMember

router = APIRouter()


@router.get("/users")
async def list_members():
    """List all project members (humans and AI agents) for the user picker."""
    async with async_session() as session:
        members = (
            await session.execute(select(ProjectMember).order_by(ProjectMember.created_at))
        ).scalars().all()
        return [
            {
                "id": str(m.id),
                "display_name": m.display_name,
                "type": m.type,
            }
            for m in members
        ]
