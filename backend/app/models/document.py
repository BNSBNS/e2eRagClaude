"""
Document Model
Location: backend/app/models/document.py
"""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from core.database import Base

class DocumentStatus(enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # File information
    original_filename = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)  # Stored filename
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # Processing status
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.UPLOADING)
    
    # Metadata and results
    metadata = Column(JSONB, default=dict)
    processing_results = Column(JSONB, default=dict)
    extracted_text = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.original_filename}, status={self.status})>"