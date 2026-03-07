import logging
import logging.config

from pydantic_settings import BaseSettings

from .memory_log_handler import MemoryLogHandler


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    database_url: str = (
        "postgresql+asyncpg://teamagent:teamagent_dev@postgres:5432/teamagent"
    )
    model: str = "claude-opus-4-6"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-preview"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    team_agent_env: str = "dev"
    api_service_url: str = "http://api:8000"
    internal_api_key: str = "team-agent-internal"
    log_level: str = "INFO"
    log_format: str = "text"


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
