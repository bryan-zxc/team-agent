import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKey, TimestampMixin


class Chat(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "chats"

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
