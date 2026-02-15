from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    database_url: str = "postgresql+asyncpg://teamagent:teamagent_dev@postgres:5432/teamagent"


settings = Settings()
