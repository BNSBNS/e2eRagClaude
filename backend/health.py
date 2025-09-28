from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from neo4j import GraphDatabase
import asyncio

router = APIRouter()

@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    checks = []
    
    # PostgreSQL check
    try:
        # Assuming you have a database session
        from .database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks.append({"service": "postgresql", "status": "healthy"})
    except Exception as e:
        checks.append({"service": "postgresql", "status": "unhealthy", "error": str(e)})
    
    # Neo4j check
    try:
        # Assuming you have a Neo4j driver instance
        from .database import neo4j_driver
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        checks.append({"service": "neo4j", "status": "healthy"})
    except Exception as e:
        checks.append({"service": "neo4j", "status": "unhealthy", "error": str(e)})
    
    # Check if any service is unhealthy
    unhealthy_services = [check for check in checks if check["status"] == "unhealthy"]
    
    if unhealthy_services:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "checks": checks}
        )
    
    return {"status": "healthy", "checks": checks, "timestamp": "2025-09-28"}