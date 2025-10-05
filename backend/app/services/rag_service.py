"""
RAG (Retrieval-Augmented Generation) Service
Combines vector search with LLM generation
"""

from typing import Dict, List
from openai import AsyncOpenAI
from services.vector_store import VectorStore
from core.config import settings
import structlog

logger = structlog.get_logger()

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class RAGService:
    """Handle RAG queries"""
    
    @staticmethod
    async def query_document(
        document_id: int,
        question: str,
        n_results: int = 5
    ) -> Dict:
        """
        Perform RAG query:
        1. Search for relevant chunks
        2. Construct prompt with context
        3. Generate answer using LLM
        """
        try:
            # Step 1: Similarity search
            search_results = await VectorStore.similarity_search(
                document_id=document_id,
                query=question,
                n_results=n_results
            )
            
            # Step 2: Construct context
            context = "\n\n".join([
                f"[Chunk {i+1}]:\n{chunk}" 
                for i, chunk in enumerate(search_results['chunks'])
            ])
            
            # Step 3: Generate answer
            system_prompt = """You are a helpful assistant that answers questions based on the provided context.
Use ONLY the information from the context to answer questions.
If the answer cannot be found in the context, say "I cannot find this information in the document."
Cite the chunk number when referencing information."""
            
            user_prompt = f"""Context from document:
{context}

Question: {question}

Answer:"""
            
            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            
            # Calculate costs (approximate)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            
            # GPT-4 pricing (as of 2024)
            input_cost = (input_tokens / 1000) * 0.03  # $0.03 per 1K tokens
            output_cost = (output_tokens / 1000) * 0.06  # $0.06 per 1K tokens
            total_cost = input_cost + output_cost
            
            logger.info("RAG query completed",
                       document_id=document_id,
                       input_tokens=input_tokens,
                       output_tokens=output_tokens,
                       cost_usd=round(total_cost, 4))
            
            return {
                'answer': answer,
                'context_chunks': search_results['chunks'],
                'distances': search_results['distances'],
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': response.usage.total_tokens,
                    'cost_usd': round(total_cost, 4)
                }
            }
            
        except Exception as e:
            logger.error("RAG query failed", error=str(e))
            raise