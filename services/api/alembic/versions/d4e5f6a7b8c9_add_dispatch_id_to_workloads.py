"""add dispatch_id to workloads

Revision ID: d4e5f6a7b8c9
Revises: b8f2e4a17c03
Create Date: 2026-03-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "b8f2e4a17c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workloads", sa.Column("dispatch_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workloads", "dispatch_id")
