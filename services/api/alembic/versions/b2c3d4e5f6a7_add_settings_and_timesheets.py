"""Add settings JSONB column and timesheets table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add settings JSONB column to project_members
    op.add_column(
        "project_members",
        sa.Column("settings", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    # 2. Migrate margin_percent data into settings
    op.execute(
        """
        UPDATE project_members
        SET settings = jsonb_build_object(
            'margin_percent', COALESCE(margin_percent, 30.0),
            'timesheet_markup', 30
        )
        """
    )

    # 3. Drop margin_percent column
    op.drop_column("project_members", "margin_percent")

    # 4. Create timesheets table
    op.create_table(
        "timesheets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("member_id", UUID(as_uuid=True), sa.ForeignKey("project_members.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("hours", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "member_id", "date", name="uq_timesheets_project_member_date"),
        sa.Index("ix_timesheets_member_date", "member_id", "date"),
    )


def downgrade() -> None:
    op.drop_table("timesheets")

    op.add_column(
        "project_members",
        sa.Column("margin_percent", sa.Float, nullable=True, server_default=sa.text("30.0")),
    )
    op.execute(
        """
        UPDATE project_members
        SET margin_percent = (settings->>'margin_percent')::float
        WHERE settings ? 'margin_percent'
        """
    )

    op.drop_column("project_members", "settings")
