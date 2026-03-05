"""GitHub Projects v2 board provisioning.

Creates and configures a GitHub Projects v2 board for new projects:
- 5 status columns (Backlog, Ready, In progress, In review, Done)
- Start date and Target date fields
- Linked to the project repository
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict

from .config import settings

logger = logging.getLogger(__name__)

GH_BIN = "/usr/bin/gh"

STATUS_OPTIONS = [
    {"name": "Backlog", "color": "GRAY", "description": ""},
    {"name": "Ready", "color": "YELLOW", "description": ""},
    {"name": "In progress", "color": "BLUE", "description": ""},
    {"name": "In review", "color": "PURPLE", "description": ""},
    {"name": "Done", "color": "GREEN", "description": ""},
]


@dataclass
class BoardConfig:
    project_number: int
    project_node_id: str
    status_field_id: str
    status_options: dict[str, str]  # {"Backlog": "f75ad846", ...}
    start_date_field_id: str
    target_date_field_id: str

    def to_dict(self) -> dict:
        return asdict(self)


async def _run_gh(*args: str) -> tuple[int, str, str]:
    """Run a gh CLI command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        GH_BIN, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


async def provision_board(project_name: str, repo_name: str) -> BoardConfig | None:
    """Provision a GitHub Projects v2 board for a newly created project.

    Returns BoardConfig on success, None on failure.
    Non-critical — caller should handle None gracefully.
    """
    owner = settings.github_owner

    # 1. Create the project
    rc, stdout, stderr = await _run_gh(
        "project", "create",
        "--title", project_name,
        "--owner", "@me",
        "--format", "json",
    )
    if rc != 0:
        logger.warning("Board creation failed: %s", stderr)
        return None

    project_data = json.loads(stdout)
    project_number = project_data["number"]
    project_node_id = project_data["id"]

    # 2. Read existing fields to get Status field ID
    rc, stdout, stderr = await _run_gh(
        "project", "field-list", str(project_number),
        "--owner", "@me",
        "--format", "json",
    )
    if rc != 0:
        logger.warning("Field list failed: %s", stderr)
        return None

    fields = json.loads(stdout)
    status_field = None
    for field in fields.get("fields", []):
        if field.get("name") == "Status":
            status_field = field
            break

    if not status_field:
        logger.warning("Status field not found on board %d", project_number)
        return None

    status_field_id = status_field["id"]

    # 3. Update Status field options via GraphQL
    options_graphql = ", ".join(
        f'{{name: "{opt["name"]}", color: {opt["color"]}, description: ""}}'
        for opt in STATUS_OPTIONS
    )

    mutation = (
        "mutation {"
        f'  updateProjectV2Field(input: {{'
        f'    fieldId: "{status_field_id}"'
        f'    singleSelectOptions: [{options_graphql}]'
        "  }) {"
        "    projectV2Field {"
        "      ... on ProjectV2SingleSelectField {"
        "        id"
        "        options { id name }"
        "      }"
        "    }"
        "  }"
        "}"
    )

    rc, stdout, stderr = await _run_gh("api", "graphql", "-f", f"query={mutation}")
    if rc != 0:
        logger.warning("Status field update failed: %s", stderr)
        return None

    result = json.loads(stdout)
    updated_options = (
        result.get("data", {})
        .get("updateProjectV2Field", {})
        .get("projectV2Field", {})
        .get("options", [])
    )
    status_options = {opt["name"]: opt["id"] for opt in updated_options}

    # 4. Add Start date field
    rc, stdout, stderr = await _run_gh(
        "project", "field-create", str(project_number),
        "--owner", "@me",
        "--name", "Start date",
        "--data-type", "DATE",
        "--format", "json",
    )
    if rc != 0:
        logger.warning("Start date field creation failed: %s", stderr)
        return None
    start_date_field_id = json.loads(stdout).get("id", "")

    # 5. Add Target date field
    rc, stdout, stderr = await _run_gh(
        "project", "field-create", str(project_number),
        "--owner", "@me",
        "--name", "Target date",
        "--data-type", "DATE",
        "--format", "json",
    )
    if rc != 0:
        logger.warning("Target date field creation failed: %s", stderr)
        return None
    target_date_field_id = json.loads(stdout).get("id", "")

    # 6. Link board to repo
    rc, _, stderr = await _run_gh(
        "project", "link", str(project_number),
        "--owner", "@me",
        "--repo", f"{owner}/{repo_name}",
    )
    if rc != 0:
        logger.warning("Board-repo link failed (non-fatal): %s", stderr)

    return BoardConfig(
        project_number=project_number,
        project_node_id=project_node_id,
        status_field_id=status_field_id,
        status_options=status_options,
        start_date_field_id=start_date_field_id,
        target_date_field_id=target_date_field_id,
    )
