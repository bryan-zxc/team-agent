"""GitHub repository creation via REST API."""

import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubError(Exception):
    """Raised when a GitHub API call fails."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"GitHub API error ({status_code}): {detail}")


async def create_repo(name: str, description: str = "") -> str:
    """Create a new GitHub repository and return its HTTPS clone URL.

    Raises GitHubError on failure.
    """
    token = settings.github_token
    if not token:
        raise GitHubError(
            500, "GitHub token not available. Check gh_auth volume mount."
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{GITHUB_API_URL}/user/repos",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "name": name,
                "description": description,
                "auto_init": False,
                "private": False,
            },
        )

    if resp.status_code == 201:
        clone_url = resp.json()["clone_url"]
        logger.info("Created GitHub repo: %s", clone_url)
        return clone_url

    if resp.status_code == 422:
        detail = resp.json().get("message", "Repository name already taken")
        raise GitHubError(422, detail)

    raise GitHubError(resp.status_code, resp.text)
