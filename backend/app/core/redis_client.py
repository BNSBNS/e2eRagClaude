"""
Redis Client Configuration
Location: backend/app/core/redis_client.py
"""

import redis.asyncio as redis
from core.config import settings
import json
from typing import Any, Optional

class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Test connection
        await self.redis.ping()
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Set a key-value pair"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        await self.redis.set(key, value, ex=expire)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key"""
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    async def delete(self, key: str):
        """Delete a key"""
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.redis.exists(key) == 1

# Global Redis client
redis_client = RedisClient()

async def init_redis():
    """Initialize Redis connection"""
    await redis_client.connect()

async def close_redis():
    """Close Redis connection"""
    await redis_client.close()

async def get_redis():
    """Dependency to get Redis client"""
    return redis_client