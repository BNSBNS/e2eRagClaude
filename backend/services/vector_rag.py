from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, TextLoader
import chromadb
from typing import List, Dict

class VectorRAGService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.embedding_model = SentenceTransformer(model_name)
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(
            name="document_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", "!", "?", ",", " "]
        )
    
    def load_document(self, file_path: str) -> List[str]:
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            text_content = "\n".join([doc.page_content for doc in documents])
        elif file_path.endswith('.txt'):
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
            text_content = documents[0].page_content
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        return self.text_splitter.split_text(text_content)
    
    def index_document(self, document_id: str, file_path: str, metadata: Dict = None):
        chunks = self.load_document(file_path)
        embeddings = self.embedding_model.encode(chunks)
        
        chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        chunk_metadata = [
            {
                "document_id": document_id,
                "chunk_index": i,
                "file_path": file_path,
                **(metadata or {})
            }
            for i in range(len(chunks))
        ]
        
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=chunk_metadata,
            ids=chunk_ids
        )
        
        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks),
            "total_embeddings": len(embeddings)
        }
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        query_embedding = self.embedding_model.encode(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                "chunk_id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "similarity_score": 1 - results['distances'][0][i]
            })
        
        return formatted_results