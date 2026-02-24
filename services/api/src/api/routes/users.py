from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..database import async_session
from ..guards import get_current_user
from ..models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/users")
async def list_users():
    """List all global users (for the landing page user picker)."""
    async with async_session() as session:
        users = (
            await session.execute(select(User).order_by(User.display_name))
        ).scalars().all()
        return [
            {
                "id": str(u.id),
                "display_name": u.display_name,
            }
            for u in users
        ]
