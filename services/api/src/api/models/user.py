from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.api.models.base import Base, UUIDPrimaryKey, TimestampMixin


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
