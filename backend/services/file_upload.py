from fastapi import UploadFile, HTTPException
from pathlib import Path
import shutil, uuid, hashlib, magic
from datetime import datetime
from typing import List, Optional

class FileUploadService:
    def __init__(self, upload_dir: Path = Path("uploads")):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(exist_ok=True)
        self.max_size = 25 * 1024 * 1024  # 25MB
        self.allowed_extensions = {'.pdf', '.txt', '.json', '.docx'}
        self.allowed_mime_types = {
            'application/pdf', 'text/plain', 
            'application/json', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
    
    async def validate_file(self, file: UploadFile) -> dict:
        result = {"valid": True, "errors": []}
        
        if not file.filename:
            result["valid"] = False
            result["errors"].append("No file selected")
            return result
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            result["valid"] = False
            result["errors"].append(f"File extension '{file_ext}' not allowed")
        
        content = await file.read()
        await file.seek(0)
        
        if len(content) > self.max_size:
            result["valid"] = False
            result["errors"].append(f"File too large ({len(content):,} bytes)")
        
        detected_mime = magic.from_buffer(content, mime=True)
        if detected_mime not in self.allowed_mime_types:
            result["valid"] = False
            result["errors"].append(f"Invalid file type: {detected_mime}")
        
        return result
    
    async def save_file(self, file: UploadFile) -> dict:
        validation = await self.validate_file(file)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail={
                "message": "File validation failed",
                "errors": validation["errors"]
            })
        
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        file_ext = Path(file.filename).suffix
        unique_filename = f"{file_hash}{file_ext}"
        file_path = self.upload_dir / unique_filename
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        metadata = {
            "id": str(uuid.uuid4()),
            "original_filename": file.filename,
            "stored_filename": unique_filename,
            "file_hash": file_hash,
            "content_type": file.content_type,
            "size": len(content),
            "upload_time": datetime.utcnow().isoformat(),
            "location": str(file_path),
            "processing_status": "pending"
        }
        
        return metadata