"""add admin room support

Revision ID: b8f2e4a17c03
Revises: a7e4b3c91d02
Create Date: 2026-03-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f2e4a17c03"
down_revision: Union[str, None] = "a7e4b3c91d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Admin room type column
    op.add_column("rooms", sa.Column("type", sa.String(), nullable=False, server_default="standard"))

    # Session lifecycle columns on chats (moved from workloads)
    op.add_column("chats", sa.Column("session_id", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("status", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("permission_mode", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # Migrate existing data from workloads to chats
    op.execute("""
        UPDATE chats SET
            session_id = w.session_id,
            status = w.status,
            updated_at = w.updated_at
        FROM workloads w WHERE chats.workload_id = w.id
    """)

    # Drop from workloads (now lives on chats)
    op.drop_column("workloads", "session_id")
    op.drop_column("workloads", "status")
    op.drop_column("workloads", "updated_at")


def downgrade() -> None:
    op.add_column("workloads", sa.Column("session_id", sa.String(), nullable=True))
    op.add_column("workloads", sa.Column("status", sa.String(), nullable=False, server_default="assigned"))
    op.add_column("workloads", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE workloads SET
            session_id = c.session_id,
            status = COALESCE(c.status, 'assigned'),
            updated_at = c.updated_at
        FROM chats c WHERE c.workload_id = workloads.id AND c.type = 'workload'
    """)
    op.drop_column("chats", "updated_at")
    op.drop_column("chats", "permission_mode")
    op.drop_column("chats", "status")
    op.drop_column("chats", "session_id")
    op.drop_column("rooms", "type")
