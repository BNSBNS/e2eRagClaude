"""
Database Connection
Location: backend/core/database.py
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from sqlalchemy import text
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
    """Initialize database - create all tables"""
    
    # Import models to register them with Base
    from models import user, document, chat
    
    async with engine.begin() as conn:
        # Drop all tables in the public schema using CASCADE
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        # Recreate the schema
        await conn.execute(text("CREATE SCHEMA public"))
        # You might need to grant permissions as well, depending on your user
        # await conn.execute(text("GRANT ALL ON SCHEMA public TO your_username"))
        # await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        
        # Now create all tables
        await conn.run_sync(Base.metadata.create_all)
        # await conn.run_sync(Base.metadata.drop_all)
        # await conn.run_sync(Base.metadata.create_all)
        # await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn))
        # await conn.run_sync(Base.metadata.create_all)
        # # Drop existing ENUM types first (they don't get dropped with tables)
        # await conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
        # await conn.execute(text("DROP TYPE IF EXISTS messagerole CASCADE"))
        
        # # Now create tables (will also create ENUM types)
        # await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


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