"""
Main FastAPI Application Entry Point
Location: backend/app/main.py
"""

# Add import
from api import auth, documents, ai, websocket as ws_router, teacher, research
import os
import sys
from pathlib import Path

# Add the app directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import structlog
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import our modules
from api import auth, documents, ai, websocket as ws_router
from core.database import init_db, close_db
from core.redis_client import init_redis, close_redis
from core.config import settings
from utils.file_utils import ensure_upload_directory

# Configure structured logging for production
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    try:
        # Startup
        logger.info("Starting AI Document Platform...")
        
        # Initialize databases
        await init_db()
        logger.info("Database initialized")
        
        await init_redis()
        logger.info("Redis initialized")
        
        # Ensure upload directory exists
        ensure_upload_directory()
        logger.info("Upload directory ready")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down AI Document Platform...")
        await close_db()
        await close_redis()

# Create FastAPI app
app = FastAPI(
    title="AI Document Processing Platform",
    version="1.0.0",
    description="Production-grade RAG application with OAuth2/JWT, Neo4j graphs, and LangGraph agents",
    lifespan=lifespan
)

# Rate limiting (protects against abuse and cost overruns)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security middleware - only in production
if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Prometheus monitoring
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[".*admin.*", "/metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app).expose(app)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Global exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai-processing"])
app.include_router(ws_router.router, prefix="/ws", tags=["websockets"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["teacher-agent"])
# Add router (remove teacher if you want)
app.include_router(research.router, prefix="/api/research", tags=["research-agent"])


# Health check endpoints
@app.get("/health", tags=["System"])
async def health_check():
    """
    Basic health check endpoint for load balancers.

    Returns immediately with status. Use /health/deep for dependency checks.
    """
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/deep", tags=["System"])
async def deep_health_check(db: AsyncSession = Depends(get_db)):
    """
    Deep health check - validates all dependencies.

    Checks:
    - Database connectivity (PostgreSQL)
    - Redis connectivity
    - OpenAI API accessibility

    Use this for monitoring/alerting, not load balancing (slower).
    """
    from datetime import datetime
    from sqlalchemy import text

    checks = {}

    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        checks["database"] = "unhealthy"

    # Check Redis
    try:
        from core.redis_client import redis_client
        await redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        checks["redis"] = "unhealthy"

    # Check OpenAI (simple API call)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        await client.models.list()
        checks["openai"] = "healthy"
    except Exception as e:
        logger.error("OpenAI health check failed", error=str(e))
        checks["openai"] = "unhealthy"

    # Overall status
    all_healthy = all("healthy" in v for v in checks.values())
    overall_status = "healthy" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Document Processing Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )