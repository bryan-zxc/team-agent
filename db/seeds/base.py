"""Shared schema and utilities for seed scripts.

Provides a database reset helper and connection function.
Schema is managed by Alembic migrations in services/api/.
"""

import asyncio
import os

import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://teamagent:teamagent_dev@localhost:5432/teamagent",
)

DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

DROP_TABLES = """
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TABLE IF EXISTS llm_usage CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS workloads CASCADE;
DROP TABLE IF EXISTS chats CASCADE;
DROP TABLE IF EXISTS rooms CASCADE;
DROP TABLE IF EXISTS project_members CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;
"""


async def reset_schema(conn: asyncpg.Connection) -> None:
    """Drop all tables then recreate via Alembic migrations."""
    await conn.execute(DROP_TABLES)
    print("Dropped existing tables")

    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "alembic", "upgrade", "head",
        cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed: {stderr.decode()}")
    print(f"Created tables via Alembic: {stdout.decode().strip()}")


async def connect() -> asyncpg.Connection:
    """Return an asyncpg connection using the standard DSN."""
    return await asyncpg.connect(DSN)
