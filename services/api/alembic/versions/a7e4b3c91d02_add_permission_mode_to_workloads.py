"""add permission_mode to workloads

Revision ID: a7e4b3c91d02
Revises: c3a7f1b2d456
Create Date: 2026-02-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7e4b3c91d02"
down_revision: Union[str, None] = "c3a7f1b2d456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workloads", sa.Column("permission_mode", sa.String(), nullable=False, server_default="default"))


def downgrade() -> None:
    op.drop_column("workloads", "permission_mode")
