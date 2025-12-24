"""
Document Processing Service
Handles document upload, processing, and management
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import UploadFile, HTTPException
from models.document import Document, DocumentStatus, RAGType
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
        document_type: str,
        rag_type: RAGType = RAGType.VECTOR  # NEW: User-selected RAG type
    ) -> Document:
        """
        Upload and process document with user-selected RAG type.

        Educational Note:
        This is where the user's RAG type choice takes effect.
        The rag_type parameter determines which databases and processing
        pipelines will be used.

        Args:
            db: Database session
            user: Current user
            file: Uploaded file
            document_type: File type identifier
            rag_type: RAG processing type (vector, graph, or hybrid)

        Processing will be:
        - VECTOR: Only ChromaDB embeddings
        - GRAPH: Only Neo4j knowledge graph
        - HYBRID: Both ChromaDB and Neo4j
        """
        try:
            # Validate file type
            file_extension = get_file_extension(file.filename)
            if file_extension not in ['.pdf', '.txt', '.csv']:
                raise HTTPException(status_code=400, detail="Unsupported file type")

            # Save file
            file_path, file_hash = await save_upload_file(file, user.id)

            # Create document record with RAG type
            document = Document(
                user_id=user.id,
                title=file.filename,
                file_path=file_path,
                file_hash=file_hash,
                content_type=file_extension.replace('.', ''),
                status=DocumentStatus.PROCESSING,
                rag_type=rag_type  # Store user's choice
            )

            db.add(document)
            await db.commit()
            await db.refresh(document)

            logger.info("Document uploaded",
                       doc_id=document.id,
                       user_id=user.id,
                       rag_type=rag_type,
                       status="pending_processing")

            # Return immediately with PENDING status
            # Processing will be handled by background task in API endpoint
            return document

        except Exception as e:
            logger.error("Document upload failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    @staticmethod
    async def process_document(db: AsyncSession, document: Document):
        """
        Process document based on user-selected RAG type.

        THIS IS THE KEY METHOD for conditional RAG processing!

        Educational Note:
        Previously, this method always processed BOTH vector and graph.
        Now it conditionally processes based on document.rag_type:
        - VECTOR only: Skip graph processing (saves time and storage)
        - GRAPH only: Skip vector processing
        - HYBRID: Process both (maximum accuracy, 2x cost)

        Processing Steps:
        1. Extract text (common for all types)
        2. Chunk text (common for all types)
        3. Conditionally process based on rag_type:
           - VECTOR: Create embeddings → ChromaDB
           - GRAPH: Extract entities → Neo4j
           - HYBRID: Both pipelines
        4. Store processing metadata
        """
        try:
            processing_meta = {}

            # STEP 1: Extract text based on file type (common for all RAG types)
            if document.content_type == 'pdf':
                extracted_data = await PDFProcessor.extract_with_metadata(document.file_path)
                document.extracted_text = extracted_data['text']
                document.doc_metadata = extracted_data['doc_metadata']

            elif document.content_type == 'txt':
                with open(document.file_path, 'r', encoding='utf-8') as f:
                    document.extracted_text = f.read()
                document.doc_metadata = {'char_count': len(document.extracted_text)}

            elif document.content_type == 'csv':
                with open(document.file_path, 'r', encoding='utf-8') as f:
                    document.extracted_text = f.read()
                document.doc_metadata = {'char_count': len(document.extracted_text)}

            # STEP 2: Chunk text (common for all RAG types)
            # Educational Note: Even graph RAG benefits from chunking for entity extraction
            chunks = TextChunker.chunk_by_tokens(
                document.extracted_text,
                chunk_size=500,
                overlap=50
            )
            document.chunk_count = len(chunks)

            logger.info("Text extracted and chunked",
                       doc_id=document.id,
                       chunk_count=len(chunks),
                       rag_type=document.rag_type)

            # STEP 3: Conditional processing based on RAG type
            # This is the KEY optimization - only process what user requested!

            if document.rag_type in [RAGType.VECTOR, RAGType.HYBRID]:
                # VECTOR PROCESSING PIPELINE
                logger.info("Processing vector embeddings",
                           doc_id=document.id)

                await VectorStore.add_document_chunks(
                    document_id=document.id,
                    chunks=chunks,
                    metadata=[{
                        'page': i // 3 + 1,
                        'chunk_index': i,
                        'rag_type': 'vector'
                    } for i in range(len(chunks))]
                )

                # Calculate average chunk length for metadata
                avg_chunk_length = sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0

                processing_meta['vector'] = {
                    'chunk_count': len(chunks),
                    'embedding_model': 'text-embedding-ada-002',
                    'collection_name': f'doc_{document.id}',
                    'avg_chunk_length': int(avg_chunk_length)
                }

                logger.info("Vector processing completed",
                           doc_id=document.id,
                           chunks_embedded=len(chunks))

            if document.rag_type in [RAGType.GRAPH, RAGType.HYBRID]:
                # GRAPH PROCESSING PIPELINE
                logger.info("Processing knowledge graph",
                           doc_id=document.id)

                # Extract entities and relationships
                # Educational Note: Entity extraction works best with longer text
                if len(document.extracted_text) > 100:
                    extraction = await EntityExtractor.extract_from_text(
                        document.extracted_text
                    )

                    entities = extraction.get('entities', [])
                    relationships = extraction.get('relationships', [])

                    await neo4j_service.create_document_graph(
                        document_id=document.id,
                        entities=entities,
                        relationships=relationships
                    )

                    # Count entity types for metadata
                    entity_types = {}
                    for entity in entities:
                        entity_type = entity.get('type', 'Unknown')
                        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

                    processing_meta['graph'] = {
                        'entity_count': len(entities),
                        'relationship_count': len(relationships),
                        'graph_id': f'doc_{document.id}',
                        'entity_types': entity_types
                    }

                    logger.info("Graph processing completed",
                               doc_id=document.id,
                               entities=len(entities),
                               relationships=len(relationships))
                else:
                    logger.warning("Document too short for graph extraction",
                                  doc_id=document.id,
                                  text_length=len(document.extracted_text))

            # STEP 4: Store processing metadata
            document.processing_metadata = processing_meta
            document.status = DocumentStatus.COMPLETED

            await db.commit()
            await db.refresh(document)

            logger.info("Document processing completed",
                       doc_id=document.id,
                       rag_type=document.rag_type,
                       metadata=processing_meta)

            # Cache chunks for quick access
            await cache_set(f"doc_chunks:{document.id}", chunks, expire=86400)

        except Exception as e:
            document.status = DocumentStatus.FAILED
            await db.commit()
            logger.error("Document processing failed",
                        doc_id=document.id,
                        rag_type=document.rag_type,
                        error=str(e))
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