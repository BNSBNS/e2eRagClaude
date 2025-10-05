"""
User Model
Location: backend/models/user.py

SQLAlchemy ORM model for users table.

Why SQLAlchemy ORM?
1. Database-agnostic: Works with PostgreSQL, MySQL, SQLite, etc.
2. Type-safe: Python classes instead of raw SQL
3. Relationships: Easy to define foreign keys and relationships
4. Migrations: Works with Alembic for schema changes
5. Security: Prevents SQL injection automatically
"""

from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLAEnum
from sqlalchemy.orm import relationship
from enum import Enum
from core.database import Base


class UserRole(str, Enum):
    """
    User roles for RBAC (Role-Based Access Control).
    
    - USER: Regular user (can upload/view own documents)
    - ADMIN: Administrator (can view/delete all documents)
    
    Future: Could add more roles like MODERATOR, VIEWER, etc.
    """
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """
    User model representing users in the system.
    
    This maps to the 'users' table in PostgreSQL.
    Each column becomes a field in the table.
    """
    __tablename__ = "users"
    
    # Primary key - auto-incrementing integer
    id = Column(Integer, primary_key=True, index=True)
    
    # Username - must be unique, indexed for fast lookups
    username = Column(String(50), unique=True, index=True, nullable=False)
    
    # Email - must be unique, indexed
    email = Column(String(100), unique=True, index=True, nullable=False)
    
    # Full name - optional
    full_name = Column(String(100), nullable=True)
    
    # Password hash - NEVER store plain passwords!
    hashed_password = Column(String(255), nullable=False)
    
    # User role - determines permissions
    role = Column(
        SQLAEnum(UserRole),
        default=UserRole.USER,
        nullable=False
    )
    
    # Active status - allows soft deletion/deactivation
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    
    # Relationship to documents (one-to-many)
    # A user can have multiple documents
    documents = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Relationship to chat sessions (one-to-many)
    # A user can have multiple chat sessions
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"