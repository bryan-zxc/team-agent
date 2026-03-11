import logging
import logging.config
from functools import cached_property
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

from .memory_log_handler import MemoryLogHandler


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://teamagent:teamagent_dev@postgres:5432/teamagent"
    )
    redis_url: str = "redis://redis:6379"
    ai_service_url: str = "http://ai-service:8001"
    team_agent_env: str = "dev"
    log_level: str = "INFO"
    log_format: str = "text"

    # OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Auth
    session_max_age_days: int = 7
    frontend_url: str = "http://localhost:3000"
    internal_api_key: str = "team-agent-internal"

    # GitHub
    github_owner: str = "bryan-zxc"

    @property
    def cookie_secure(self) -> bool:
        return self.team_agent_env == "prod"

    @cached_property
    def github_token(self) -> str | None:
        """Read GitHub OAuth token from gh CLI auth config (mounted volume)."""
        hosts_path = Path("/home/agent/.config/gh/hosts.yml")
        if not hosts_path.exists():
            return None
        try:
            hosts = yaml.safe_load(hosts_path.read_text())
            return hosts.get("github.com", {}).get("oauth_token")
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to read GitHub token from %s",
                hosts_path,
                exc_info=True,
            )
            return None


settings = Settings()
memory_handler = MemoryLogHandler(capacity=1000)


def setup_logging() -> None:
    """Configure logging from settings. Call once at startup."""
    if settings.log_format == "json":
        formatter_config = {
            "class": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    else:
        formatter_config = {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": formatter_config,
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["console"],
            },
        }
    )

    memory_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    )
    logging.getLogger().addHandler(memory_handler)
