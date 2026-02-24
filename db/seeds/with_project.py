"""Seed: users + popmart project with Zimomo agent.

Drops/recreates all tables. Inserts users, a fully-formed project with:
- Real git clone of https://github.com/bryan-zxc/popmart.git
- Zimomo coordinator agent (profile written to {clone_path}/.team-agent/agents/zimomo.md)
- Manifest file written to {clone_path}/.team-agent/manifest.json
- Alice and Bob as human members
- No rooms — rooms are created through the UI
- Initial commit with manifest + Zimomo profile (not pushed — local dev only)

No LLM calls — the agent profile is written directly by the seed.

Usage: docker compose exec api .venv/bin/python db/seeds/with_project.py
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from base import connect, reset_schema

GIT_REPO_URL = "https://github.com/bryan-zxc/popmart.git"
CLONE_BASE = Path("/data/projects")

ZIMOMO_PROFILE = """\
# Zimomo

## Pronoun
he/him

## Personality
Authoritative, calm, and composed. He acts as a protective patriarch who prefers order over chaos. He interacts with a serious, guiding tone, providing firm direction and expecting adherence to structure. He does not engage in frivolity, focusing instead on leading the user through complex tasks with a steady hand.

## Specialisation
analysis and reporting

## Work Done
"""


async def seed():
    conn = await connect()
    try:
        await reset_schema(conn)

        now = datetime.now(timezone.utc)

        # --- Users ---
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

        # --- Write manifest and Zimomo profile into the cloned repo ---
        team_agent_dir = Path(clone_path) / ".team-agent"
        agents_dir = team_agent_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "version": 1,
            "env": "dev",
            "project_id": str(project_id),
            "project_name": "popmart",
            "claimed_at": now.isoformat(),
        }
        (team_agent_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print("Wrote manifest.json")

        profile_path = agents_dir / "zimomo.md"
        profile_path.write_text(ZIMOMO_PROFILE)
        print(f"Wrote Zimomo profile to {profile_path}")

        # --- Initial commit (local only — don't push to upstream in dev seed) ---
        async def _run_git(*args: str) -> None:
            proc = await asyncio.create_subprocess_exec(
                "git", *args,
                cwd=clone_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"  git {' '.join(args)} failed: {stderr.decode().strip()}")

        await _run_git("add", ".team-agent/")
        await _run_git(
            "-c", "user.name=seed",
            "-c", "user.email=seed@team-agent",
            "commit", "-m", "Initial seed: manifest + Zimomo profile",
        )
        print("Committed .team-agent/ to local repo")

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
            zimomo_member_id, project_id, "Zimomo", "coordinator", now,
        )
        print("Inserted 3 members (Alice, Bob, Zimomo)")

        print("Seed complete — popmart project ready")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
