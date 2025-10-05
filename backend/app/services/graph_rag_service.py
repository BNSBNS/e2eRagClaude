"""
Graph RAG Service
Combines Neo4j graph queries with LLM generation
"""

from typing import Dict
from openai import AsyncOpenAI
from services.neo4j_service import neo4j_service
from core.config import settings
import structlog

logger = structlog.get_logger()

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class GraphRAGService:
    """Graph-based RAG queries"""
    
    @staticmethod
    async def query_document(document_id: int, question: str) -> Dict:
        """Perform graph RAG query"""
        
        # Step 1: Query the graph
        graph_paths = await neo4j_service.query_graph(document_id, question)
        
        if not graph_paths:
            return {
                'answer': "No relevant information found in the knowledge graph.",
                'graph_paths': [],
                'usage': {}
            }
        
        # Step 2: Construct context from graph
        context = "Knowledge Graph Information:\n"
        for path in graph_paths:
            context += f"- {path['entity1']} {path['relationship']} {path['entity2']}\n"
        
        # Step 3: Generate answer
        system_prompt = """You are a helpful assistant that answers questions using information from a knowledge graph.
Use the graph relationships to provide accurate, well-reasoned answers.
Explain how the entities relate to each other when relevant."""
        
        user_prompt = f"""{context}

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
        
        # Calculate costs
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        total_cost = (input_tokens / 1000) * 0.03 + (output_tokens / 1000) * 0.06
        
        logger.info("Graph RAG query completed",
                   document_id=document_id,
                   paths_found=len(graph_paths),
                   cost_usd=round(total_cost, 4))
        
        return {
            'answer': answer,
            'graph_paths': graph_paths,
            'usage': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': response.usage.total_tokens,
                'cost_usd': round(total_cost, 4)
            }
        }