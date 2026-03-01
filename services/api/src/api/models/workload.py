import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKey, TimestampMixin


class Workload(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "workloads"

    main_chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    worktree_branch: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dispatch_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    permission_mode: Mapped[str] = mapped_column(String, nullable=False, default="default", server_default="default")
