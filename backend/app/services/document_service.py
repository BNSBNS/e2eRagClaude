"""
Document Processing Service
Handles document upload, processing, and management
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import UploadFile, HTTPException
from models.document import Document, DocumentStatus
from models.user import User
from services.pdf_processor import PDFProcessor, TextChunker
from utils.file_utils import save_upload_file, delete_file, get_file_extension
from core.redis_client import cache_set, cache_get, cache_delete
import structlog
from services.vector_store import VectorStore
from services.entity_extractor import EntityExtractor
from services.neo4j_service import neo4j_service

logger = structlog.get_logger()


class DocumentService:
    """Service for document operations"""
    
    @staticmethod
    async def upload_document(
        db: AsyncSession,
        user: User,
        file: UploadFile,
        document_type: str
    ) -> Document:
        """Upload and process document"""
        try:
            # Validate file type
            file_extension = get_file_extension(file.filename)
            if file_extension not in ['.pdf', '.txt', '.csv']:
                raise HTTPException(status_code=400, detail="Unsupported file type")
            
            # Save file
            file_path, file_hash = await save_upload_file(file, user.id)
            
            # Create document record
            document = Document(
                user_id=user.id,
                title=file.filename,
                file_path=file_path,
                file_hash=file_hash,
                content_type=file_extension.replace('.', ''),
                status=DocumentStatus.PROCESSING
            )
            
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            logger.info("Document uploaded", doc_id=document.id, user_id=user.id)
            
            # Process document asynchronously (in background)
            # For now, we'll do it synchronously
            await DocumentService.process_document(db, document)
            
            return document
            
        except Exception as e:
            logger.error("Document upload failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    @staticmethod
    async def process_document(db: AsyncSession, document: Document):
        """Extract text and prepare for RAG"""
        try:
            # Extract text based on file type
            if document.content_type == 'pdf':
                extracted_data = await PDFProcessor.extract_with_metadata(document.file_path)
                document.extracted_text = extracted_data['text']
                document.doc_metadata  = extracted_data['metadata']
                
            elif document.content_type == 'txt':
                with open(document.file_path, 'r', encoding='utf-8') as f:
                    document.extracted_text = f.read()
                document.doc_metadata  = {'char_count': len(document.extracted_text)}
            
            elif document.content_type == 'csv':
                with open(document.file_path, 'r', encoding='utf-8') as f:
                    document.extracted_text = f.read()
                # Could parse CSV here for structured processing
            
            # Chunk text for RAG
            chunks = TextChunker.chunk_by_tokens(document.extracted_text, chunk_size=500, overlap=50)
            document.chunk_count = len(chunks)
            
            await VectorStore.add_document_chunks(
            document_id=document.id,
            chunks=chunks,
            metadata=[{'page': i // 3 + 1} for i in range(len(chunks))]  # Approximate page numbers
            )

            if document.content_type == 'pdf' and len(document.extracted_text) > 100:
                extraction = await EntityExtractor.extract_from_text(document.extracted_text)
                await neo4j_service.create_document_graph(
                    document_id=document.id,
                    entities=extraction.get('entities', []),
                    relationships=extraction.get('relationships', [])
                )

            # Update status
            document.status = DocumentStatus.COMPLETED
            
            await db.commit()
            await db.refresh(document)
            
            logger.info("Document processed", doc_id=document.id, chunks=len(chunks))
            
            # Store chunks for later use (we'll implement vector storage in Phase 3)
            await cache_set(f"doc_chunks:{document.id}", chunks, expire=86400)  # 24 hours
            
        except Exception as e:
            document.status = DocumentStatus.FAILED
            await db.commit()
            logger.error("Document processing failed", doc_id=document.id, error=str(e))
            raise
    
    @staticmethod
    async def get_user_documents(db: AsyncSession, user: User) -> List[Document]:
        """Get all documents for a user"""
        try:
            # Try cache first
            cache_key = f"user_docs:{user.id}"
            cached = await cache_get(cache_key)
            if cached:
                return cached
            
            # Query database
            result = await db.execute(
                select(Document)
                .where(Document.user_id == user.id)
                .order_by(Document.created_at.desc())
            )
            documents = result.scalars().all()
            
            # Cache for 5 minutes
            await cache_set(cache_key, [doc.id for doc in documents], expire=300)
            
            return documents
            
        except Exception as e:
            logger.error("Get documents failed", user_id=user.id, error=str(e))
            raise
    
    @staticmethod
    async def get_document_by_id(db: AsyncSession, document_id: int, user: User) -> Optional[Document]:
        """Get specific document"""
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user.id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def delete_document(db: AsyncSession, document_id: int, user: User):
        """Delete document"""
        try:
            document = await DocumentService.get_document_by_id(db, document_id, user)
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Delete file from disk
            await delete_file(document.file_path)
            
            # Delete from database
            await db.delete(document)
            await db.commit()
            
            # Clear cache
            await cache_delete(f"user_docs:{user.id}")
            await cache_delete(f"doc_chunks:{document_id}")
            
            logger.info("Document deleted", doc_id=document_id)
            
        except Exception as e:
            logger.error("Document deletion failed", doc_id=document_id, error=str(e))
            raise