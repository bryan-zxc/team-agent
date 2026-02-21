"""Shared schema and utilities for seed scripts.

Provides DROP/CREATE SQL and a database connection helper.
All seed scenarios import from this module.
"""

import os

import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://teamagent:teamagent_dev@localhost:5432/teamagent",
)

DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

DROP_TABLES = """
DROP TABLE IF EXISTS llm_usage CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS chats CASCADE;
DROP TABLE IF EXISTS rooms CASCADE;
DROP TABLE IF EXISTS project_members CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;
"""

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    git_repo_url TEXT,
    clone_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_members (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    user_id UUID REFERENCES users(id),
    display_name TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, display_name)
);

CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY,
    room_id UUID NOT NULL REFERENCES rooms(id),
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    chat_id UUID NOT NULL REFERENCES chats(id),
    member_id UUID NOT NULL REFERENCES project_members(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);

CREATE TABLE IF NOT EXISTS llm_usage (
    id UUID PRIMARY KEY,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost FLOAT NOT NULL,
    request_type TEXT NOT NULL,
    caller TEXT NOT NULL,
    session_id TEXT,
    num_turns INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_llm_usage_caller_created_at ON llm_usage(caller, created_at);
"""


async def reset_schema(conn: asyncpg.Connection) -> None:
    """Drop and recreate all tables."""
    await conn.execute(DROP_TABLES)
    print("Dropped existing tables")
    await conn.execute(CREATE_TABLES)
    print("Created tables")


async def connect() -> asyncpg.Connection:
    """Return an asyncpg connection using the standard DSN."""
    return await asyncpg.connect(DSN)
