"""
Documents API Router
Handles document upload, retrieval, and deletion
"""

from typing import List, Annotated
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.user import User, UserRole
from models.document import Document, DocumentStatus
from api.auth import get_current_active_user, require_admin
from services.document_service import DocumentService
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Response Models
class DocumentResponse(BaseModel):
    id: int
    title: str
    content_type: str
    status: DocumentStatus
    chunk_count: int | None
    created_at: datetime
    doc_metadata : dict | None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    data: List[DocumentResponse]
    total: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for processing.
    
    Supported formats: PDF, TXT, CSV
    """
    logger.info("Document upload request", user_id=current_user.id, filename=file.filename)
    
    # Validate file size (50MB limit)
    content = await file.read()
    await file.seek(0)  # Reset file pointer
    
    if len(content) > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    
    document = await DocumentService.upload_document(
        db=db,
        user=current_user,
        file=file,
        document_type=document_type
    )
    
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
        "metadata": document.doc_metadata 
    }