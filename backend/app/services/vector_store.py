"""
Vector Store Service
Handles embeddings and similarity search using ChromaDB
"""

from typing import List, Dict, Optional

from chromadb.config import Settings
from openai import AsyncOpenAI
from core.config import settings
import structlog
import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import settings

logger = structlog.get_logger()

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Initialize ChromaDB client
chroma_client = chromadb.HttpClient(
    host=settings.CHROMA_HOST,
    port=settings.CHROMA_PORT,
    settings=ChromaSettings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

class VectorStore:
    """Manage document embeddings and similarity search"""
    
    @staticmethod
    async def create_embeddings(texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI"""
        try:
            response = await openai_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            logger.info("Embeddings created", count=len(embeddings))
            return embeddings
        except Exception as e:
            logger.error("Embedding creation failed", error=str(e))
            raise
    
    @staticmethod
    def get_or_create_collection(document_id: int):
        """Get or create a ChromaDB collection for a document"""
        collection_name = f"doc_{document_id}"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            logger.info("Retrieved existing collection", collection=collection_name)
        except:
            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Created new collection", collection=collection_name)
        
        return collection
    
    @staticmethod
    async def add_document_chunks(
        document_id: int,
        chunks: List[str],
        metadata: Optional[List[Dict]] = None
    ):
        """Add document chunks to vector store"""
        try:
            collection = VectorStore.get_or_create_collection(document_id)
            
            # Generate embeddings
            embeddings = await VectorStore.create_embeddings(chunks)
            
            # Prepare IDs and metadata
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            metadatas = metadata or [{"chunk_index": i} for i in range(len(chunks))]
            
            # Add to collection
            collection.add(
                embeddings=embeddings,
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
            
            logger.info("Chunks added to vector store", 
                       document_id=document_id, 
                       count=len(chunks))
            
        except Exception as e:
            logger.error("Failed to add chunks", error=str(e))
            raise
    
    @staticmethod
    async def similarity_search(
        document_id: int,
        query: str,
        n_results: int = 5
    ) -> Dict:
        """Search for similar chunks"""
        try:
            collection = VectorStore.get_or_create_collection(document_id)
            
            # Generate query embedding
            query_embedding = (await VectorStore.create_embeddings([query]))[0]
            
            # Search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            logger.info("Similarity search completed", 
                       document_id=document_id,
                       results_count=len(results['documents'][0]))
            
            return {
                'chunks': results['documents'][0],
                'distances': results['distances'][0],
                'metadatas': results['metadatas'][0]
            }
            
        except Exception as e:
            logger.error("Similarity search failed", error=str(e))
            raise
    
    @staticmethod
    def delete_document_collection(document_id: int):
        """Delete a document's vector collection"""
        try:
            collection_name = f"doc_{document_id}"
            chroma_client.delete_collection(name=collection_name)
            logger.info("Collection deleted", collection=collection_name)
        except Exception as e:
            logger.error("Collection deletion failed", error=str(e))