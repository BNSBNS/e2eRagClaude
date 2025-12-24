"""
Documents API Router
Handles document upload, retrieval, and deletion
"""

from typing import List, Annotated
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.user import User, UserRole
from models.document import Document, DocumentStatus, RAGType
from api.auth import get_current_active_user, require_admin
from services.document_service import DocumentService
import structlog
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# BACKGROUND TASK HELPERS
# ============================================================================

async def _process_document_background(document_id: int):
    """
    Background task for document processing.

    This function runs asynchronously after the upload request returns.
    Benefits:
    - User gets immediate response (no 30-120 second wait)
    - Multiple uploads can process concurrently
    - No HTTP timeout issues

    Note: Creates its own database session since background tasks
    run outside the request context.
    """
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # Fetch document
            document = await db.get(Document, document_id)
            if not document:
                logger.error("Document not found for processing", document_id=document_id)
                return

            # Process document (vector, graph, or hybrid)
            await DocumentService.process_document(db, document)

            logger.info("Document processing completed",
                       document_id=document_id,
                       status="completed")

        except Exception as e:
            logger.error("Background processing failed",
                        document_id=document_id,
                        error=str(e),
                        exc_info=True)

            # Update document status to FAILED
            try:
                document.status = DocumentStatus.FAILED
                await db.commit()
            except:
                pass  # Best effort


# Response Models
class DocumentResponse(BaseModel):
    id: int
    title: str
    content_type: str
    status: DocumentStatus
    chunk_count: int | None
    created_at: datetime
    doc_metadata : dict | None
    rag_type: RAGType | None  # NEW: RAG processing type
    processing_metadata: dict | None  # NEW: Processing details

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    data: List[DocumentResponse]
    total: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Max 5 uploads per minute per IP (prevents abuse)
async def upload_document(
    background_tasks: BackgroundTasks,  # NEW: Background task processing (no default)
    file: UploadFile = File(...),
    document_type: str = Form(...),
    rag_type: str = Form(default="vector"),  # NEW: User selects RAG type
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for processing with user-selected RAG type.

    Educational Note:
    This endpoint now allows users to choose their RAG processing type.
    This is a KEY feature that gives users control over how their documents
    are processed and which databases are used.

    Parameters:
    - file: Document file (PDF, TXT, CSV)
    - document_type: File type identifier
    - rag_type: "vector", "graph", or "hybrid" (NEW!)

    RAG Type Explanation:
    - "vector": Fast semantic search using embeddings (ChromaDB)
    - "graph": Relationship reasoning using knowledge graphs (Neo4j)
    - "hybrid": Both approaches for maximum accuracy

    Processing Based on RAG Type:
    - vector: Creates embeddings, stores in ChromaDB
    - graph: Extracts entities/relationships, stores in Neo4j
    - hybrid: Both vector and graph processing (2x time/storage)

    Supported formats: PDF, TXT, CSV
    Max file size: 50MB
    """
    logger.info("Document upload request",
               user_id=current_user.id,
               filename=file.filename,
               rag_type=rag_type)

    # Validate RAG type
    try:
        selected_rag_type = RAGType(rag_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid RAG type: '{rag_type}'. Must be 'vector', 'graph', or 'hybrid'"
        )

    # Validate file size (50MB limit)
    content = await file.read()
    await file.seek(0)  # Reset file pointer

    if len(content) > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    # Upload with RAG type
    document = await DocumentService.upload_document(
        db=db,
        user=current_user,
        file=file,
        document_type=document_type,
        rag_type=selected_rag_type  # Pass RAG type to service
    )

    # Schedule document processing in background (non-blocking)
    # This allows the upload request to return immediately
    background_tasks.add_task(
        _process_document_background,
        document_id=document.id
    )

    logger.info("Document uploaded, processing scheduled",
               document_id=document.id,
               rag_type=document.rag_type,
               status="processing_scheduled")

    return document


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all documents for current user"""
    documents = await DocumentService.get_user_documents(db, current_user)
    
    return {
        "data": documents,
        "total": len(documents)
    }


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get specific document"""
    document = await DocumentService.get_document_by_id(db, document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete document.
    Regular users can only delete their own documents.
    Admins can delete any document.
    """
    document = await DocumentService.get_document_by_id(db, document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    if current_user.role != UserRole.ADMIN and document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    await DocumentService.delete_document(db, document_id, current_user)
    
    return None


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get extracted text content from document"""
    document = await DocumentService.get_document_by_id(db, document_id, current_user)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document still processing")
    
    return {
        "document_id": document.id,
        "title": document.title,
        "content": document.extracted_text,
        "doc_metadata": document.doc_metadata 
    }