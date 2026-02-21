from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKey, TimestampMixin


class Project(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    git_repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    clone_path: Mapped[str | None] = mapped_column(String, nullable=True)
