# app/services/file_handler.py
from typing import List, Optional
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from app.models.document import Document
from app.core.database import get_db

class FileProcessor:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
    
    async def process_upload(self, file: UploadFile, user_id: str) -> Document:
        # Validate file
        if file.content_type not in ["application/pdf", "text/plain"]:
            raise HTTPException(400, "Unsupported file type")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = f"uploads/{user_id}/{file_id}_{file.filename}"
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Create document record
        document = Document(
            id=file_id,
            user_id=user_id,
            filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type,
            status="processing"
        )
        
        # Process asynchronously
        await self.process_document_async(document)
        return document
    
    async def process_document_async(self, document: Document):
        try:
            # Extract text
            if document.mime_type == "application/pdf":
                loader = PyPDFLoader(document.file_path)
                pages = loader.load()
                text = "\n".join([page.page_content for page in pages])
            else:
                async with aiofiles.open(document.file_path, 'r') as f:
                    text = await f.read()
            
            # Create chunks
            chunks = self.text_splitter.split_text(text)
            
            # Generate embeddings
            embeddings = self.embeddings.embed_documents(chunks)
            
            # Store in vector database
            await self.store_in_vectordb(document.id, chunks, embeddings)
            
            # Update document status
            document.status = "processed"
            document.processing_results = {
                "chunks": len(chunks),
                "total_tokens": sum(len(chunk) for chunk in chunks)
            }
            
        except Exception as e:
            document.status = "failed"
            document.processing_results = {"error": str(e)}