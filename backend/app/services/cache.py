# app/services/cache.py
import hashlib
import json
from typing import Any, Optional
from app.core.redis import redis_client

class IntelligentCache:
    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate deterministic cache key"""
        key_data = json.dumps(kwargs, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    async def get_or_set(self, prefix: str, generator_func, ttl: Optional[int] = None, **kwargs) -> Any:
        """Get from cache or generate and cache"""
        cache_key = self._generate_cache_key(prefix, **kwargs)
        
        # Try to get from cache
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return json.loads(cached_result)
        
        # Generate result
        result = await generator_func(**kwargs)
        
        # Cache result
        await redis_client.setex(
            cache_key,
            ttl or self.default_ttl,
            json.dumps(result, default=str)
        )
        
        return result
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)

# Usage in RAG service
cache = IntelligentCache()

async def cached_rag_query(query: str, user_id: str, rag_mode: str):
    return await cache.get_or_set(
        prefix=f"rag:{rag_mode}",
        generator_func=perform_rag_query,
        ttl=1800,  # 30 minutes
        query=query,
        user_id=user_id,
        rag_mode=rag_mode
    )