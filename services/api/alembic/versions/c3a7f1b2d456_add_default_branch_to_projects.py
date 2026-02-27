"""add default_branch to projects

Revision ID: c3a7f1b2d456
Revises: 9b5dc581fa67
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a7f1b2d456"
down_revision: Union[str, None] = "9b5dc581fa67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("default_branch", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "default_branch")
