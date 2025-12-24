"""
Database Connection
Location: backend/core/database.py
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings
import structlog

logger = structlog.get_logger()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database schema using Alembic migrations.

    PRODUCTION SAFETY:
    - Does NOT drop existing schema (preserves all data)
    - Only creates tables if they don't exist
    - For schema changes, use Alembic migrations instead

    CRITICAL: Never use DROP commands in production - this would destroy all data!
    """

    # Import models to register them with Base
    from models import user, document, chat

    async with engine.begin() as conn:
        # Create tables only if they don't exist (idempotent operation)
        # This preserves existing data and schema
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized (existing data preserved)")


async def close_db():
    """Close database connection"""
    await engine.dispose()
    logger.info("Database connection closed")


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()