"""
PDF Processing Service
Extracts text from PDF files
"""

from typing import List, Dict
import PyPDF2
import pdfplumber
from pathlib import Path
import structlog

logger = structlog.get_logger()


class PDFProcessor:
    """Process PDF files and extract text"""
    
    @staticmethod
    async def extract_text_pypdf(file_path: str) -> str:
        """Extract text using PyPDF2 (faster but less accurate)"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page.extract_text()
            
            logger.info("PDF text extracted (PyPDF2)", pages=len(pdf_reader.pages))
            return text
        except Exception as e:
            logger.error("PyPDF2 extraction failed", error=str(e))
            raise
    
    @staticmethod
    async def extract_text_pdfplumber(file_path: str) -> str:
        """Extract text using pdfplumber (slower but more accurate)"""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text += f"\n--- Page {page_num + 1} ---\n"
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
            
            logger.info("PDF text extracted (pdfplumber)", pages=len(pdf.pages))
            return text
        except Exception as e:
            logger.error("pdfplumber extraction failed", error=str(e))
            raise
    
    @staticmethod
    async def extract_with_metadata(file_path: str) -> Dict:
        """Extract text with metadata"""
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = pdf.doc_metadata 
                num_pages = len(pdf.pages)
                
                # Extract text with page boundaries
                pages_content = []
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        pages_content.append({
                            'page_number': page_num + 1,
                            'text': page_text,
                            'char_count': len(page_text)
                        })
                
                full_text = "\n\n".join([p['text'] for p in pages_content])
                
                return {
                    'text': full_text,
                    'pages': pages_content,
                    'metadata': {
                        'title': metadata.get('Title', ''),
                        'author': metadata.get('Author', ''),
                        'subject': metadata.get('Subject', ''),
                        'num_pages': num_pages,
                        'total_chars': len(full_text)
                    }
                }
        except Exception as e:
            logger.error("PDF metadata extraction failed", error=str(e))
            raise
    
    @staticmethod
    async def extract_text(file_path: str, method: str = 'pdfplumber') -> str:
        """
        Extract text from PDF
        method: 'pypdf' or 'pdfplumber'
        """
        if method == 'pypdf':
            return await PDFProcessor.extract_text_pypdf(file_path)
        else:
            return await PDFProcessor.extract_text_pdfplumber(file_path)


# Text chunking utility
class TextChunker:
    """Split text into chunks for processing"""
    
    @staticmethod
    def chunk_by_tokens(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks by approximate token count
        1 token ≈ 4 characters
        """
        char_chunk_size = chunk_size * 4
        char_overlap = overlap * 4
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + char_chunk_size
            
            # Don't cut in the middle of a word
            if end < text_length:
                # Find last space before end
                while end > start and text[end] not in [' ', '\n', '.', '!', '?']:
                    end -= 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - char_overlap
        
        logger.info("Text chunked", num_chunks=len(chunks), chunk_size=chunk_size)
        return chunks
    
    @staticmethod
    def chunk_by_paragraphs(text: str, max_chunk_size: int = 2000) -> List[str]:
        """Split text by paragraphs, combining small ones"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += "\n\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks