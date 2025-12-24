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
from pydantic import Field, field_validator
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

    # SECRET_KEY for JWT tokens - MUST BE RANDOM AND SECRET!
    # Generate with: openssl rand -hex 32
    # NO DEFAULT - must be set via environment variable
    SECRET_KEY: str = Field(..., min_length=32)
    
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
    # Can be set via environment variable as comma-separated list
    # Default for development includes localhost and Docker internal
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://frontend:3000"],
        description="Allowed CORS origins (comma-separated in env)"
    )

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from environment variable (comma-separated)."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # ========================================================================
    # AI / ML
    # ========================================================================
    
    # OpenAI API key - REQUIRED
    # Must start with 'sk-' and be set via environment variable
    OPENAI_API_KEY: str = Field(..., min_length=20)
    
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    ALGORITHM: str = "HS256"

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 4000
    CHROMA_URL: str = "http://chromadb:4000"


    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY is secure and not the default value."""
        # Check if it's the old insecure default
        if "your-secret-key-change-this" in v.lower():
            raise ValueError(
                "Default SECRET_KEY detected! NEVER use in production. "
                "Generate a secure key with: openssl rand -hex 32"
            )

        # Ensure minimum length for security
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")

        return v

    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate OpenAI API key format."""
        if not v or v == "":
            raise ValueError(
                "OPENAI_API_KEY is required. Set it in environment variables."
            )

        # OpenAI keys start with 'sk-'
        if not v.startswith("sk-"):
            raise ValueError(
                "OPENAI_API_KEY appears invalid (should start with 'sk-'). "
                "Get your API key from https://platform.openai.com/api-keys"
            )

        return v

    class Config:
        """Pydantic config"""
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()