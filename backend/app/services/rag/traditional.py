# app/services/rag/traditional.py
from typing import List, Dict
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings

class TraditionalRAG:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = Chroma(
            embedding_function=self.embeddings,
            persist_directory="./chroma_db"
        )
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=OpenAI(temperature=0),
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 5})
        )
    
    async def query(self, question: str, user_id: str) -> Dict:
        # Add user context to retrieval
        retriever = self.vectorstore.as_retriever(
            search_kwargs={
                "k": 5,
                "filter": {"user_id": user_id}
            }
        )
        
        # Get relevant documents
        docs = retriever.get_relevant_documents(question)
        
        # Generate answer
        response = self.qa_chain.run(question)
        
        return {
            "answer": response,
            "sources": [doc.metadata for doc in docs],
            "method": "traditional_rag"
        }