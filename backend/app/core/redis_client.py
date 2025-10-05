"""
Redis Client Configuration
Handles caching, session storage, and real-time features
"""

import redis.asyncio as redis
from typing import Optional, Any
import json
from core.config import settings
import structlog

logger = structlog.get_logger()

# Global redis client
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10
        )
        # Test connection
        await redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        raise


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


async def get_redis() -> redis.Redis:
    """Get Redis client instance"""
    return redis_client


# Cache utilities
async def cache_set(key: str, value: Any, expire: int = 3600):
    """Set cache with expiration (default 1 hour)"""
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await redis_client.setex(key, expire, value)
    except Exception as e:
        logger.error("Cache set failed", key=key, error=str(e))


async def cache_get(key: str) -> Optional[Any]:
    """Get cache value"""
    try:
        value = await redis_client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    except Exception as e:
        logger.error("Cache get failed", key=key, error=str(e))
        return None


async def cache_delete(key: str):
    """Delete cache key"""
    try:
        await redis_client.delete(key)
    except Exception as e:
        logger.error("Cache delete failed", key=key, error=str(e))


async def cache_clear_pattern(pattern: str):
    """Delete all keys matching pattern"""
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.error("Cache clear pattern failed", pattern=pattern, error=str(e))