"""Seed the database with dev data.

Drops and recreates all tables, then inserts sample data for the
"popmart" project with human users, an AI agent, a room, and messages.
This is a dev-only script — not for production use.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

import asyncpg


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://teamagent:teamagent_dev@localhost:5432/teamagent",
)

# asyncpg uses postgresql:// not postgresql+asyncpg://
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


async def seed():
    conn = await asyncpg.connect(DSN)

    try:
        await conn.execute(DROP_TABLES)
        print("Dropped existing tables")

        await conn.execute(CREATE_TABLES)
        print("Created tables")

        now = datetime.now(timezone.utc)

        # Users (humans only)
        alice_id = uuid.uuid4()
        bob_id = uuid.uuid4()

        await conn.execute(
            "INSERT INTO users (id, display_name, created_at) VALUES ($1, $2, $3)",
            alice_id, "Alice", now,
        )
        await conn.execute(
            "INSERT INTO users (id, display_name, created_at) VALUES ($1, $2, $3)",
            bob_id, "Bob", now,
        )
        print("Inserted 2 users (Alice, Bob)")

        # Project
        project_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO projects (id, name, created_at) VALUES ($1, $2, $3)",
            project_id, "popmart", now,
        )
        print("Inserted project: popmart")

        # Project members (humans only — AI agents are created via generate_agent_profile)
        alice_member_id = uuid.uuid4()
        bob_member_id = uuid.uuid4()

        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            alice_member_id, project_id, alice_id, "Alice", "human", now,
        )
        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            bob_member_id, project_id, bob_id, "Bob", "human", now,
        )
        print("Inserted 2 project members (Alice, Bob)")

        # Room (project-scoped)
        room_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO rooms (id, project_id, name, created_at) VALUES ($1, $2, $3, $4)",
            room_id, project_id, "General", now,
        )
        print("Inserted room: General")

        # Primary chat
        chat_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO chats (id, room_id, type, created_at) VALUES ($1, $2, $3, $4)",
            chat_id, room_id, "primary", now,
        )
        print("Inserted primary chat")

        # Messages (using member_id)
        messages = [
            (uuid.uuid4(), chat_id, alice_member_id, "Hey team, how's it going?", now),
            (uuid.uuid4(), chat_id, bob_member_id, "All good! Just setting things up.", now),
        ]
        await conn.executemany(
            "INSERT INTO messages (id, chat_id, member_id, content, created_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            messages,
        )
        print("Inserted 2 messages")

        print("Seed complete!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
