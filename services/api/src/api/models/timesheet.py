import datetime
import uuid

from sqlalchemy import Date, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPrimaryKey, TimestampMixin


class Timesheet(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "timesheets"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "member_id", "date", name="uq_timesheets_project_member_date"
        ),
        Index("ix_timesheets_member_date", "member_id", "date"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id"), nullable=False
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False)
