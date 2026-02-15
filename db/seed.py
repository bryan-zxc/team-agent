"""Seed the database with dev data.

Creates tables from raw SQL (no Alembic yet) and inserts sample users,
a room, a primary chat, and a few messages. Idempotent — skips if
the tables already contain data.
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


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY,
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
    user_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);
"""


async def seed():
    conn = await asyncpg.connect(DSN)

    try:
        await conn.execute(CREATE_TABLES)
        print("Tables created (or already exist)")

        existing = await conn.fetchval("SELECT COUNT(*) FROM users")
        if existing > 0:
            print("Seed data already exists, skipping")
            return

        now = datetime.now(timezone.utc)

        alice_id = uuid.uuid4()
        bob_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        room_id = uuid.uuid4()
        chat_id = uuid.uuid4()

        await conn.execute(
            "INSERT INTO users (id, display_name, type, created_at) VALUES ($1, $2, $3, $4)",
            alice_id, "Alice", "human", now,
        )
        await conn.execute(
            "INSERT INTO users (id, display_name, type, created_at) VALUES ($1, $2, $3, $4)",
            bob_id, "Bob", "human", now,
        )
        await conn.execute(
            "INSERT INTO users (id, display_name, type, created_at) VALUES ($1, $2, $3, $4)",
            agent_id, "Zimomo", "ai", now,
        )
        print("Inserted 3 users (Alice, Bob, Zimomo)")

        await conn.execute(
            "INSERT INTO rooms (id, name, created_at) VALUES ($1, $2, $3)",
            room_id, "General", now,
        )
        print("Inserted room: General")

        await conn.execute(
            "INSERT INTO chats (id, room_id, type, created_at) VALUES ($1, $2, $3, $4)",
            chat_id, room_id, "primary", now,
        )
        print("Inserted primary chat")

        messages = [
            (uuid.uuid4(), chat_id, alice_id, "Hey team, how's it going?", now),
            (uuid.uuid4(), chat_id, bob_id, "All good! Just setting things up.", now),
            (uuid.uuid4(), chat_id, agent_id, "Hello! I'm here to help whenever you need me.", now),
        ]
        await conn.executemany(
            "INSERT INTO messages (id, chat_id, user_id, content, created_at) VALUES ($1, $2, $3, $4, $5)",
            messages,
        )
        print("Inserted 3 messages")

        print("Seed complete!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
