"""
Research Agent API
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from models.user import User
from api.auth import get_current_active_user
from services.document_service import DocumentService
from services.agents.research_agent import research_agent
from models.document import DocumentStatus
import structlog

logger = structlog.get_logger()

router = APIRouter()


class ResearchRequest(BaseModel):
    document_id: int
    query: str


class ResearchResponse(BaseModel):
    answer: str
    plan: list[str]
    findings: list[dict]
    cost: float


@router.post("/research", response_model=ResearchResponse)
async def research_document(
    request: ResearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Research a document using autonomous agent.
    
    The agent will:
    1. Create a research plan
    2. Execute research steps
    3. Validate findings
    4. Loop back if needed
    5. Synthesize final answer
    """
    logger.info("Research request", 
               document_id=request.document_id,
               user_id=current_user.id)
    
    # Get document
    document = await DocumentService.get_document_by_id(db, request.document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    # Run research
    result = await research_agent.research(
        document_id=document.id,
        document_text=document.extracted_text,
        query=request.query
    )
    
    return result