"""Seed: clean slate with users only.

Drops/recreates all tables. Inserts two global users (Alice, Bob).
No projects — use this to test the project creation flow.

Usage: docker compose exec api .venv/bin/python db/seeds/clean.py
"""

import asyncio
import uuid
from datetime import datetime, timezone

from base import connect, reset_schema


async def seed():
    conn = await connect()
    try:
        await reset_schema(conn)

        now = datetime.now(timezone.utc)
        alice_id = uuid.uuid4()
        bob_id = uuid.uuid4()

        await conn.execute(
            "INSERT INTO users (id, display_name, email, created_at) VALUES ($1, $2, $3, $4)",
            alice_id, "Alice", "alice@example.com", now,
        )
        await conn.execute(
            "INSERT INTO users (id, display_name, email, created_at) VALUES ($1, $2, $3, $4)",
            bob_id, "Bob", "bob@example.com", now,
        )
        print("Inserted 2 users (Alice, Bob)")
        print("Seed complete — clean slate")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
