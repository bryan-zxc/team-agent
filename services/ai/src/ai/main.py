import asyncio
import logging

import redis.asyncio as aioredis

from src.ai.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-service")


async def main():
    client = aioredis.from_url(settings.redis_url)

    try:
        await client.ping()
        logger.info("AI service connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        return

    logger.info("AI service listening (idle — no triggers configured yet)")

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        await client.aclose()
        logger.info("AI service shut down")


if __name__ == "__main__":
    asyncio.run(main())
