"""Add tool_approval_events table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_approval_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("chat_id", UUID(as_uuid=True), sa.ForeignKey("chats.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tool_name", sa.String, nullable=False),
        sa.Column("decision", sa.String, nullable=False),
        sa.Column("approval_request_id", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Index("ix_tool_approval_events_chat_created", "chat_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("tool_approval_events")
