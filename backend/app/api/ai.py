"""
AI Processing API Router
Handles RAG queries and AI interactions
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from services.graph_rag_service import GraphRAGService

from core.database import get_db
from models.user import User
from api.auth import get_current_active_user
from services.document_service import DocumentService
from services.rag_service import RAGService
from models.document import DocumentStatus
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Request/Response Models
class QueryRequest(BaseModel):
    question: str
    method: str = "rag"  # "rag" or "graph" (graph to be implemented)


class QueryResponse(BaseModel):
    answer: str
    context_chunks: list[str]
    distances: list[float]
    usage: dict


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/query/{document_id}", response_model=QueryResponse)
async def query_document(
    document_id: int,
    request: QueryRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Query a document using RAG.
    
    - Finds relevant chunks using semantic search
    - Generates answer using GPT-4 with context
    - Returns answer with sources and token usage
    """
    logger.info("AI query request", 
               document_id=document_id, 
               user_id=current_user.id,
               method=request.method)
    
    # Verify document exists and belongs to user
    document = await DocumentService.get_document_by_id(db, document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    # Perform RAG query
    if request.method == "rag":
        result = await RAGService.query_document(
            document_id=document_id,
            question=request.question
        )
        return result
    
    elif request.method == "graph":
        result = await GraphRAGService.query_document(
            document_id=document_id,
            question=request.question
        )
        return result
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")