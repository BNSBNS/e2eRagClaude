"""
Main FastAPI Application Entry Point
Location: backend/app/main.py
"""

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

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
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