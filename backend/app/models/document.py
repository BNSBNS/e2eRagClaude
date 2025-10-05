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
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="documents")
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"