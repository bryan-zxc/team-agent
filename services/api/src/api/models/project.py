from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKey, TimestampMixin


class Project(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    git_repo_url: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    clone_path: Mapped[str | None] = mapped_column(String, nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
