"""add cost tracking columns

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_usage",
        sa.Column(
            "member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_members.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "llm_usage",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_llm_usage_member_created_at",
        "llm_usage",
        ["member_id", "created_at"],
    )
    op.add_column(
        "project_members",
        sa.Column("margin_percent", sa.Float(), nullable=True, server_default="30.0"),
    )


def downgrade() -> None:
    op.drop_column("project_members", "margin_percent")
    op.drop_index("ix_llm_usage_member_created_at", table_name="llm_usage")
    op.drop_column("llm_usage", "project_id")
    op.drop_column("llm_usage", "member_id")
