import logging.config

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://teamagent:teamagent_dev@postgres:5432/teamagent"
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

    @property
    def cookie_secure(self) -> bool:
        return self.team_agent_env == "prod"


settings = Settings()


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

    logging.config.dictConfig({
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
    })
