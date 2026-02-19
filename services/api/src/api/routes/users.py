from fastapi import APIRouter
from sqlalchemy import select

from ..database import async_session
from ..models.user import User

router = APIRouter()


@router.get("/users")
async def list_users():
    async with async_session() as session:
        users = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
        return [
            {
                "id": str(u.id),
                "display_name": u.display_name,
                "type": u.type,
            }
            for u in users
        ]
