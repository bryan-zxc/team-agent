from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.api.models.base import Base, UUIDPrimaryKey, TimestampMixin


class Room(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "rooms"

    name: Mapped[str] = mapped_column(String, nullable=False)
