"""
Application Configuration
Location: backend/app/core/config.py
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # For Windows with Docker Desktop
    DATABASE_URL: str = "postgresql://postgres:postgres@host.docker.internal:5432/ai_platform"
    REDIS_URL: str = "redis://host.docker.internal:6379/0"
    NEO4J_URI: str = "bolt://host.docker.internal:7687"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_platform"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # File uploads
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    UPLOAD_DIRECTORY: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt", ".csv"]
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()