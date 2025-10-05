"""
Chat Models
Location: backend/app/models/chat.py
"""

import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from core.database import Base
from sqlalchemy.dialects.postgresql import UUID


class MessageRole(str, enum.Enum):
    """Role of message sender"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(Base):
    """
    Chat session model.

    Stores chat conversations between users and the AI.
    """

    __tablename__ = "chat_sessions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to users table
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Session title
    title = Column(String(500))

    # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    meta_data = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self):
        return (
            f"<ChatSession(id={self.id}, user_id={self.user_id}, title='{self.title}')>"
        )


class ChatMessage(Base):
    """
    Individual chat message model.

    Stores individual messages within a chat session.
    """

    __tablename__ = "chat_messages"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to chat_sessions table
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message role (user, assistant, system)
    role = Column(SQLEnum(MessageRole), nullable=False)

    # Message content
    content = Column(Text, nullable=False)

    # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    # Can store: sources, token costs, model used, etc.
    meta_data = Column(JSONB, default=dict)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role}, session_id={self.session_id})>"
