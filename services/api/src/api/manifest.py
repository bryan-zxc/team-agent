"""Manifest file operations for repo ownership.

Every project claims ownership of its git repo via .team-agent/manifest.json.
This module is the single source of truth for reading, writing, and validating
that manifest. See ADR-0008 for the full ownership model.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_DIR = ".team-agent"
MANIFEST_PATH = f"{MANIFEST_DIR}/manifest.json"
MANIFEST_VERSION = 1


class ManifestStatus(str, Enum):
    VALID = "valid"
    UNCLAIMED = "unclaimed"
    CLAIMED_PROD = "claimed_prod"
    CLAIMED_OTHER = "claimed_other"
    CORRECTED = "corrected"
    LOCKED = "locked"
    ERROR = "error"


@dataclass
class ManifestCheckResult:
    status: ManifestStatus
    manifest: dict | None = None
    reason: str | None = None


async def _run_git(*args: str, cwd: str) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


def read_manifest(clone_path: str | Path) -> dict | None:
    """Read and parse manifest.json. Returns None if not found or invalid."""
    manifest_file = Path(clone_path) / MANIFEST_PATH
    if not manifest_file.exists():
        return None
    try:
        return json.loads(manifest_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read manifest at %s: %s", manifest_file, e)
        return None


def write_manifest(
    clone_path: str | Path,
    project_id: str,
    project_name: str,
    env: str,
) -> dict:
    """Write manifest.json and return the manifest dict."""
    manifest = {
        "version": MANIFEST_VERSION,
        "env": env,
        "project_id": project_id,
        "project_name": project_name,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_dir = Path(clone_path) / MANIFEST_DIR
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest


async def git_commit_and_push(clone_path: str | Path, message: str) -> tuple[bool, str]:
    """Stage .team-agent/, commit, and push. Returns (success, error_message)."""
    cwd = str(clone_path)

    rc, _, stderr = await _run_git("add", ".team-agent/", cwd=cwd)
    if rc != 0:
        return False, f"git add failed: {stderr}"

    rc, _, stderr = await _run_git(
        "-c", "user.name=team-agent",
        "-c", "user.email=noreply@team-agent",
        "commit", "-m", message,
        cwd=cwd,
    )
    if rc != 0 and "nothing to commit" not in stderr:
        return False, f"git commit failed: {stderr}"

    rc, _, stderr = await _run_git("push", cwd=cwd)
    if rc != 0:
        return False, f"git push failed: {stderr}"

    return True, ""


def check_unclaimed(clone_path: str | Path) -> ManifestCheckResult:
    """Check if a repo is unclaimed (for project creation).

    Returns UNCLAIMED if no manifest, CLAIMED_PROD if prod-owned, CLAIMED_OTHER otherwise.
    """
    manifest = read_manifest(clone_path)
    if manifest is None:
        return ManifestCheckResult(status=ManifestStatus.UNCLAIMED)

    if manifest.get("env") == "prod":
        return ManifestCheckResult(
            status=ManifestStatus.CLAIMED_PROD,
            manifest=manifest,
            reason=(
                f"This repository is owned by production project "
                f"'{manifest.get('project_name')}'. Choose a different repository."
            ),
        )

    return ManifestCheckResult(
        status=ManifestStatus.CLAIMED_OTHER,
        manifest=manifest,
        reason=(
            f"This repository is owned by project "
            f"'{manifest.get('project_name')}' in the '{manifest.get('env')}' environment."
        ),
    )


async def validate_manifest(
    clone_path: str | Path,
    project_id: str,
    project_name: str,
    env: str,
    pull: bool = True,
) -> ManifestCheckResult:
    """Validate manifest ownership against the expected project.

    Args:
        clone_path: Path to the cloned repo.
        project_id: Expected project_id that should own this repo.
        project_name: Project name (used if force-correcting in prod).
        env: Current environment from TEAM_AGENT_ENV.
        pull: Whether to git pull first (False for post-workload checks).
    """
    cwd = str(clone_path)

    if pull:
        rc, _, stderr = await _run_git("pull", "--ff-only", cwd=cwd)
        if rc != 0:
            logger.warning("git pull failed for %s: %s", cwd, stderr)

    manifest = read_manifest(clone_path)

    if manifest is None:
        return ManifestCheckResult(
            status=ManifestStatus.ERROR,
            reason="No manifest file found. The project may need to be re-initialised.",
        )

    if manifest.get("project_id") == project_id:
        return ManifestCheckResult(status=ManifestStatus.VALID, manifest=manifest)

    # Ownership mismatch
    if env == "prod":
        new_manifest = write_manifest(clone_path, project_id, project_name, env)
        success, error = await git_commit_and_push(
            clone_path, "fix: correct manifest ownership",
        )
        if success:
            return ManifestCheckResult(
                status=ManifestStatus.CORRECTED,
                manifest=new_manifest,
                reason="Manifest was corrected and pushed.",
            )
        return ManifestCheckResult(
            status=ManifestStatus.LOCKED,
            manifest=manifest,
            reason=f"Manifest mismatch. Push failed: {error}. Project locked.",
        )

    # Dev/other: immediate lockdown
    return ManifestCheckResult(
        status=ManifestStatus.LOCKED,
        manifest=manifest,
        reason=(
            f"Manifest belongs to project '{manifest.get('project_name')}' "
            f"(ID: {manifest.get('project_id')}), not this project. "
            "Fix the repo manually or create a new project with a different repo."
        ),
    )
