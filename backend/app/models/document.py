"""
Document Model
Enhanced with processing status and metadata
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Enum as SQLAEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from core.database import Base


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RAGType(str, Enum):
    """
    RAG processing type selected by user.

    Educational Note:
    Different RAG approaches have different strengths and use cases.
    Users can choose based on their needs:

    VECTOR: Traditional semantic similarity search
      - Best for: Finding similar concepts, Q&A, summarization
      - How it works: Embeds text into vectors, finds nearest neighbors using cosine similarity
      - Speed: Fast retrieval (milliseconds), scales to millions of chunks
      - Storage: Vector database (ChromaDB)
      - Use when: You need quick answers based on semantic meaning

    GRAPH: Knowledge graph with entity relationships
      - Best for: Understanding connections, multi-hop reasoning, "how/why" questions
      - How it works: Extracts entities and relationships, traverses graph paths
      - Speed: Slower processing, excellent for complex reasoning
      - Storage: Graph database (Neo4j)
      - Use when: You need to understand relationships and connections

    HYBRID: Both vector and graph (for advanced use cases)
      - Best for: Maximum accuracy, research applications, complex domains
      - How it works: Processes both, synthesizes results from both approaches
      - Trade-off: 2x storage and processing time, but highest quality answers
      - Use when: Accuracy is more important than speed/cost
    """
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


class Document(Base):
    """Document model"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # File information
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)  # pdf, txt, csv
    
    # Processing
    status = Column(SQLAEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    extracted_text = Column(Text, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    doc_metadata  = Column(JSON, nullable=True)

    # RAG Configuration (NEW)
    rag_type = Column(
        SQLAEnum(RAGType),
        nullable=True,  # Null for legacy documents
        default=RAGType.VECTOR,
        index=True,  # Index for filtering documents by RAG type
        doc="""
        User-selected RAG processing type.
        Determines which databases and processing pipelines are used:
        - VECTOR: Only ChromaDB vector embeddings
        - GRAPH: Only Neo4j knowledge graph
        - HYBRID: Both vector and graph processing
        """
    )

    processing_metadata = Column(
        JSON,
        nullable=True,
        doc="""
        Detailed processing information for each RAG type.

        Structure:
        {
            "vector": {
                "chunk_count": int,
                "embedding_model": str,
                "collection_name": str,
                "avg_chunk_length": int
            },
            "graph": {
                "entity_count": int,
                "relationship_count": int,
                "graph_id": str,
                "entity_types": list
            }
        }

        Educational Note:
        This metadata helps users understand how their document was processed
        and enables debugging/optimization of the RAG pipeline.
        """
    )
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="documents")
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"