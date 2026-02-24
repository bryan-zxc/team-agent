"""add auth sessions and user email

Revision ID: 9b5dc581fa67
Revises: 6f091083e756
Create Date: 2026-02-24 08:42:49.545905
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b5dc581fa67'
down_revision: Union[str, None] = '6f091083e756'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
    op.add_column('users', sa.Column('avatar_url', sa.String(), nullable=True))

    op.create_table(
        'sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_sessions_expires_at', 'sessions')
    op.drop_index('ix_sessions_user_id', 'sessions')
    op.drop_table('sessions')
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'email')
