import asyncio
import logging

import redis.asyncio as aioredis

from .config import settings, setup_logging
from .cost.models import Base
from .database import engine
from .listener import listen

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    # Create cost tracking table if it doesn't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    client = aioredis.from_url(settings.redis_url)

    try:
        await client.ping()
        logger.info("AI service connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        return

    try:
        await listen(client)
    except asyncio.CancelledError:
        pass
    finally:
        await client.aclose()
        logger.info("AI service shut down")


if __name__ == "__main__":
    asyncio.run(main())
