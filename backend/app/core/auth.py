# # app/core/auth.py
# from datetime import datetime, timedelta
# import json
# from typing import Optional
# import uuid
# import jwt
# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from passlib.context import CryptContext
# import redis.asyncio as redis
# from app.core.config import settings

# security = HTTPBearer()
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# redis_client = redis.Redis.from_url(settings.REDIS_URL)

# class AuthService:
#     def verify_password(self, plain_password: str, hashed_password: str) -> bool:
#         return pwd_context.verify(plain_password, hashed_password)
    
#     def get_password_hash(self, password: str) -> str:
#         return pwd_context.hash(password)
    
#     def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
#         to_encode = data.copy()
#         if expires_delta:
#             expire = datetime.utcnow() + expires_delta
#         else:
#             expire = datetime.utcnow() + timedelta(minutes=15)
#         to_encode.update({"exp": expire})
#         return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    
#     async def create_session(self, user_data: dict) -> str:
#         session_id = str(uuid.uuid4())
#         await redis_client.hset(
#             f"session:{session_id}",
#             mapping={
#                 "user_data": json.dumps(user_data),
#                 "created_at": datetime.utcnow().isoformat()
#             }
#         )
#         await redis_client.expire(f"session:{session_id}", 900)
#         return session_id

# auth_service = AuthService()

# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     try:
#         payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
#         user_id: str = payload.get("sub")
#         if user_id is None:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user_id
#     except jwt.PyJWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")