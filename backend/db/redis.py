import redis.asyncio as aioredis
import logging
from config import settings

logger = logging.getLogger(__name__)

# Strictly pulling from your centralized configuration
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

async def check_redis_connection():
    """Verifies the cache is reachable on server startup."""
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis cache.")
    except Exception as e:
        logger.error(f"Redis connection failed. Ensure Docker container is running. Error: {e}")