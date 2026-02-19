from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    database_url: str = "postgresql+asyncpg://teamagent:teamagent_dev@postgres:5432/teamagent"
    model: str = "claude-opus-4-6"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-preview"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"


settings = Settings()
