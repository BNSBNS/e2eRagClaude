"""
Configuration Settings
Location: backend/core/config.py

Centralized configuration using Pydantic Settings.
Reads from environment variables with validation.

Why Pydantic Settings?
1. Type validation: Ensures config values are correct type
2. Environment variables: Easy to configure per environment
3. Default values: Fallbacks for development
4. Documentation: Self-documenting config
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Application settings.
    
    These are loaded from environment variables or .env file.
    Pydantic validates the types automatically.
    """
    
    # ========================================================================
    # APPLICATION
    # ========================================================================
    
    APP_NAME: str = "AI Document Processing Platform"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True
    
    # ========================================================================
    # SECURITY
    # ========================================================================
    
    # SECRET_KEY for JWT tokens - MUST BE RANDOM AND SECRET IN PRODUCTION!
    # Generate with: openssl rand -hex 32
    SECRET_KEY: str = "your-secret-key-change-this-in-production-use-openssl-rand-hex-32"
    
    # ========================================================================
    # DATABASE
    # ========================================================================
    
    # PostgreSQL connection
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/ai_platform"
    
    # Redis connection
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Neo4j connection
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "your-neo4j-password"
    
    # ========================================================================
    # CORS (Cross-Origin Resource Sharing)
    # ========================================================================
    
    # Allowed origins for frontend
    # In production, set this to your actual frontend domain
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js development
        "http://frontend:3000",   # Docker internal
    ]
    
    # ========================================================================
    # AI / ML
    # ========================================================================
    
    # OpenAI API key
    OPENAI_API_KEY: str = "your-openai-api-key-here"
    
    # Model selection
    OPENAI_MODEL: str = "gpt-4"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    
    # ========================================================================
    # FILE UPLOAD
    # ========================================================================
    
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB
    
    # ========================================================================
    # MONITORING
    # ========================================================================
    
    PROMETHEUS_ENABLED: bool = True
    GRAFANA_ENABLED: bool = True
    
    class Config:
        """Pydantic config"""
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()