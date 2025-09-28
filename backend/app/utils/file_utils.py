# In backend/app/utils/file_utils.py
import os
from pathlib import Path

def ensure_upload_directory():
    """Create upload directory - Windows compatible"""
    upload_dir = Path(settings.UPLOAD_DIRECTORY)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Windows file permissions
    if os.name == 'nt':  # Windows
        import stat
        upload_dir.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)