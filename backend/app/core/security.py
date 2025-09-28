# app/core/security.py
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
import redis.asyncio as redis
import time
import hashlib

class RateLimiter:
    def __init__(self, redis_client, requests_per_minute: int = 100):
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
        
    async def is_allowed(self, user_id: str, endpoint: str) -> bool:
        key = f"rate_limit:{user_id}:{endpoint}"
        current_time = int(time.time())
        window_start = current_time - 60
        
        await self.redis.zremrangebyscore(key, 0, window_start)
        current_requests = await self.redis.zcard(key)
        
        if current_requests >= self.requests_per_minute:
            return False
            
        await self.redis.zadd(key, {str(current_time): current_time})
        await self.redis.expire(key, 60)
        return True

class SecurityHeaders:
    @staticmethod
    def add_security_headers(response):
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", 
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self';"
            )
        })
        return response