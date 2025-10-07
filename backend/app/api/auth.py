"""
Authentication API Router
Location: backend/api/auth.py

This module handles all authentication-related endpoints including:
- User registration (signup)
- User login (JWT token generation)
- Token refresh
- User profile management

OAuth2 with JWT Flow:
1. User submits credentials → 2. Backend validates → 3. JWT token generated
4. Token sent to frontend → 5. Frontend stores token → 6. Token sent in headers
7. Backend validates token → 8. Access granted/denied
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field
import structlog

from core.database import get_db
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    
)
from core.config import settings
from models.user import User, UserRole
from sqlalchemy import select

from typing import Annotated, Union
from pydantic import BaseModel

# Add this model for JSON login
class LoginJSON(BaseModel):
    """JSON login request body"""
    username: str
    password: str

logger = structlog.get_logger()

router = APIRouter()

# OAuth2 scheme for JWT token extraction from headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============================================================================
# PYDANTIC MODELS (Request/Response schemas)
# ============================================================================

class UserCreate(BaseModel):
    """Schema for user registration"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None


class UserResponse(BaseModel):
    """Schema for user data response (no password)"""
    id: int
    username: str
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy models


class Token(BaseModel):
    """JWT token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Data extracted from JWT token"""
    username: str | None = None


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency that extracts and validates JWT token, returns current user.
    
    This function is used as a dependency in protected routes.
    Flow:
    1. Extract token from Authorization header
    2. Decode and validate token
    3. Get user from database
    4. Return user object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode the JWT token
    username = decode_access_token(token)
    if username is None:
        raise credentials_exception
    
    # Fetch user from database
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Dependency that ensures user is active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Dependency that ensures user has admin role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    Process:
    1. Check if username/email already exists
    2. Hash the password (never store plain text!)
    3. Create user in database
    4. Return user data (without password)
    
    Security: Passwords are hashed using bcrypt before storage
    """
    logger.info("User signup attempt", username=user_data.username)
    
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with hashed password
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole.USER  # Default role
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info("User created successfully", user_id=new_user.id)
    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    """Login with username or email"""
    logger.info("Login attempt", username=form_data.username)
    
    # Try username first
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    # Verify password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    
    # Create token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Get current user's profile.
    
    This is a protected route - requires valid JWT token.
    The get_current_active_user dependency extracts the token,
    validates it, and returns the user object.
    """
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db)
):
    """
    List all users (Admin only).
    
    This demonstrates role-based access control (RBAC).
    Only users with ADMIN role can access this endpoint.
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users