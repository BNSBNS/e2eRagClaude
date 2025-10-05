"""
File Upload and Processing Utilities
"""

import os
import hashlib
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
import aiofiles
from core.config import settings
import structlog

logger = structlog.get_logger()


def ensure_upload_directory():
    """Create upload directory if it doesn't exist"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory ready", path=str(upload_dir))


def get_file_hash(content: bytes) -> str:
    """Generate SHA256 hash of file content"""
    return hashlib.sha256(content).hexdigest()


def get_file_extension(filename: str) -> str:
    """Get file extension"""
    return Path(filename).suffix.lower()


def is_allowed_file(filename: str) -> bool:
    """Check if file type is allowed"""
    allowed_extensions = {'.pdf', '.txt', '.csv', '.docx'}
    return get_file_extension(filename) in allowed_extensions


async def save_upload_file(upload_file: UploadFile, user_id: int) -> tuple[str, str]:
    """
    Save uploaded file to disk
    Returns: (file_path, file_hash)
    """
    try:
        # Read file content
        content = await upload_file.read()
        
        # Generate hash for deduplication
        file_hash = get_file_hash(content)
        
        # Create user-specific directory
        user_dir = Path(settings.UPLOAD_DIR) / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename
        extension = get_file_extension(upload_file.filename)
        safe_filename = f"{file_hash}{extension}"
        file_path = user_dir / safe_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info("File saved", path=str(file_path), size=len(content))
        return str(file_path), file_hash
        
    except Exception as e:
        logger.error("File save failed", error=str(e))
        raise


async def delete_file(file_path: str):
    """Delete file from disk"""
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info("File deleted", path=str(file_path))
    except Exception as e:
        logger.error("File delete failed", path=file_path, error=str(e))
        raise


async def read_file_content(file_path: str) -> bytes:
    """Read file content"""
    try:
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    except Exception as e:
        logger.error("File read failed", path=file_path, error=str(e))
        raise