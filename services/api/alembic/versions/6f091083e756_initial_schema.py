"""Initial schema

Revision ID: 6f091083e756
Revises:
Create Date: 2026-02-24 06:23:03.624027
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f091083e756'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Independent tables first
    op.create_table('users',
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('projects',
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('git_repo_url', sa.String(), nullable=True),
        sa.Column('clone_path', sa.String(), nullable=True),
        sa.Column('is_locked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('lock_reason', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('git_repo_url'),
        sa.UniqueConstraint('name'),
    )
    op.create_table('llm_usage',
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False),
        sa.Column('request_type', sa.String(), nullable=False),
        sa.Column('caller', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('num_turns', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_usage_caller_created_at', 'llm_usage', ['caller', 'created_at'], unique=False)

    # Tables with FK dependencies
    op.create_table('project_members',
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'display_name', name='uq_project_members_project_display_name'),
    )
    op.create_table('rooms',
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # chats — created WITHOUT workload_id FK (circular dependency with workloads)
    op.create_table('chats',
        sa.Column('room_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('owner_id', sa.UUID(), nullable=True),
        sa.Column('workload_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['project_members.id']),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # workloads — references chats and project_members
    op.create_table('workloads',
        sa.Column('main_chat_id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='assigned', nullable=False),
        sa.Column('worktree_branch', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['main_chat_id'], ['chats.id']),
        sa.ForeignKeyConstraint(['member_id'], ['project_members.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Now add the deferred FK: chats.workload_id → workloads.id
    op.create_foreign_key('fk_chats_workload_id', 'chats', 'workloads', ['workload_id'], ['id'])

    # messages — references chats and project_members
    op.create_table('messages',
        sa.Column('chat_id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id']),
        sa.ForeignKeyConstraint(['member_id'], ['project_members.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_messages_created_at', 'messages', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_created_at', table_name='messages')
    op.drop_table('messages')
    op.drop_constraint('fk_chats_workload_id', 'chats', type_='foreignkey')
    op.drop_table('workloads')
    op.drop_table('chats')
    op.drop_table('rooms')
    op.drop_table('project_members')
    op.drop_index('ix_llm_usage_caller_created_at', table_name='llm_usage')
    op.drop_table('llm_usage')
    op.drop_table('projects')
    op.drop_table('users')
