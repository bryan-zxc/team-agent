"""Seed: users + popmart project with Zimomo agent.

Drops/recreates all tables. Inserts users, a fully-formed project with:
- Real git clone of https://github.com/bryan-zxc/popmart.git
- Zimomo AI agent (uses pre-written profile at agents/popmart/zimomo.md)
- Alice and Bob as human members
- No rooms — rooms are created through the UI

No LLM calls — the agent profile already exists on disk.

Usage: docker compose exec api .venv/bin/python db/seeds/with_project.py
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from base import connect, reset_schema

GIT_REPO_URL = "https://github.com/bryan-zxc/popmart.git"
CLONE_BASE = Path("/data/projects")
AGENTS_DIR = Path("/app/agents")


async def seed():
    conn = await connect()
    try:
        await reset_schema(conn)

        now = datetime.now(timezone.utc)

        # --- Users ---
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

        # --- Project ---
        project_id = uuid.uuid4()
        clone_path = str(CLONE_BASE / str(project_id) / "repo")

        clone_dir = Path(clone_path)
        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", GIT_REPO_URL, clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode().strip()}")
        print(f"Cloned {GIT_REPO_URL} to {clone_path}")

        await conn.execute(
            "INSERT INTO projects (id, name, git_repo_url, clone_path, created_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            project_id, "popmart", GIT_REPO_URL, clone_path, now,
        )
        print("Inserted project: popmart")

        # --- Verify agent profile exists on disk ---
        agents_project_dir = AGENTS_DIR / "popmart"
        agents_project_dir.mkdir(parents=True, exist_ok=True)
        profile_path = agents_project_dir / "zimomo.md"
        if not profile_path.exists():
            raise RuntimeError(
                f"Zimomo profile not found at {profile_path}. "
                "Ensure agents/popmart/zimomo.md exists in the repo."
            )
        print(f"Zimomo profile verified at {profile_path}")

        # --- Members ---
        alice_member_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            alice_member_id, project_id, alice_id, "Alice", "human", now,
        )

        bob_member_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            bob_member_id, project_id, bob_id, "Bob", "human", now,
        )

        zimomo_member_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO project_members (id, project_id, user_id, display_name, type, created_at) "
            "VALUES ($1, $2, NULL, $3, $4, $5)",
            zimomo_member_id, project_id, "Zimomo", "ai", now,
        )
        print("Inserted 3 members (Alice, Bob, Zimomo)")

        print("Seed complete — popmart project ready")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
