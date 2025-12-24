"""
AI Processing API Router
Handles RAG queries and AI interactions

This router now uses specialized autonomous agents:
- Vector RAG Agent: For documents processed with vector/hybrid RAG
- Graph RAG Agent: For documents processed with graph/hybrid RAG

The routing is AUTOMATIC based on the document's rag_type field.
Users don't need to specify which method to use - the system uses the
processing type they selected at upload time.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

# New agent imports
from services.agents.vector_rag_agent import vector_rag_agent
from services.agents.graph_rag_agent import graph_rag_agent

from core.database import get_db
from models.user import User
from api.auth import get_current_active_user
from services.document_service import DocumentService
from models.document import DocumentStatus, RAGType
import structlog
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# Request/Response Models
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)  # Limit query length to prevent abuse
    # Note: method is no longer used - routing is automatic based on document.rag_type


class QueryResponse(BaseModel):
    """
    Unified response format for both Vector and Graph RAG agents.

    Fields are designed to work with both agent types:
    - Vector RAG: Returns answer with context chunks and confidence
    - Graph RAG: Returns answer with reasoning chain and graph paths
    - Hybrid: Returns combined results from both agents
    """
    answer: str
    confidence: float = 0.0

    # Vector RAG specific (optional)
    context_chunks: list[dict] = []

    # Graph RAG specific (optional)
    reasoning_chain: list[str] = []
    graph_paths: list[dict] = []

    # Common metadata
    metadata: dict = {}


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/query/{document_id}", response_model=QueryResponse)
@limiter.limit("20/minute")  # Max 20 queries per minute per IP (prevents cost overrun)
async def query_document(
    document_id: int,
    request: QueryRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Query a document using the appropriate RAG agent.

    AUTOMATIC ROUTING:
    ------------------
    The system automatically selects the right agent based on how the
    document was processed (determined by document.rag_type):

    - VECTOR → Vector RAG Agent (semantic similarity search)
    - GRAPH → Graph RAG Agent (relationship reasoning)
    - HYBRID → Both agents, synthesized answer

    This ensures users get the optimal retrieval method for their chosen
    processing type, without needing to manually specify which to use.

    EDUCATIONAL NOTE:
    -----------------
    Why automatic routing?
    1. Consistency: Use the same RAG type for both processing and querying
    2. Optimization: Each agent is specialized for its RAG type
    3. User-friendly: No need to remember which method to use
    4. Data integrity: Can't query graph if graph wasn't created

    Example:
    User uploads with "vector" → Document processed with embeddings only
    User queries → System uses Vector RAG Agent (can't use Graph, no graph exists)
    """
    logger.info(
        "AI query request",
        document_id=document_id,
        user_id=current_user.id
    )

    # Verify document exists and belongs to user
    document = await DocumentService.get_document_by_id(db, document_id, current_user)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for queries. Status: {document.status.value}"
        )

    # Route to appropriate agent based on document's RAG type
    rag_type = document.rag_type or RAGType.VECTOR  # Default to vector if null

    logger.info("Routing to agent", rag_type=rag_type.value)

    try:
        if rag_type == RAGType.VECTOR:
            # Use Vector RAG Agent for semantic similarity search
            result = await vector_rag_agent.query(
                document_id=document_id,
                user_query=request.question
            )

            return QueryResponse(
                answer=result['answer'],
                confidence=result['confidence'],
                context_chunks=result.get('context_chunks', []),
                metadata=result.get('metadata', {})
            )

        elif rag_type == RAGType.GRAPH:
            # Use Graph RAG Agent for relationship reasoning
            result = await graph_rag_agent.query(
                document_id=document_id,
                user_query=request.question
            )

            return QueryResponse(
                answer=result['answer'],
                confidence=result['confidence'],
                reasoning_chain=result.get('reasoning_chain', []),
                graph_paths=result.get('graph_paths', []),
                metadata=result.get('metadata', {})
            )

        elif rag_type == RAGType.HYBRID:
            # Run BOTH agents and synthesize results
            # This provides the most comprehensive answer at 2x cost

            logger.info("Running hybrid query - both Vector and Graph agents")

            # Run both agents in parallel with error handling
            import asyncio

            # Create tasks
            vector_task = asyncio.create_task(
                vector_rag_agent.query(document_id, request.question)
            )
            graph_task = asyncio.create_task(
                graph_rag_agent.query(document_id, request.question)
            )

            # Run with exception handling (return_exceptions=True)
            results = await asyncio.gather(vector_task, graph_task, return_exceptions=True)

            # Check which agents succeeded
            vector_result = results[0] if not isinstance(results[0], Exception) else None
            graph_result = results[1] if not isinstance(results[1], Exception) else None

            # Graceful degradation based on what succeeded
            if vector_result and graph_result:
                # IDEAL: Both agents succeeded - synthesize full answer
                synthesized_answer = await _synthesize_hybrid_answer(
                    question=request.question,
                    vector_answer=vector_result['answer'],
                    graph_answer=graph_result['answer'],
                    vector_confidence=vector_result['confidence'],
                    graph_confidence=graph_result['confidence']
                )
                combined_confidence = (
                    vector_result['confidence'] * 0.5 +
                    graph_result['confidence'] * 0.5
                )
                combined_metadata = {
                    'vector_metadata': vector_result.get('metadata', {}),
                    'graph_metadata': graph_result.get('metadata', {}),
                    'synthesis_method': 'llm_fusion',
                    'both_agents_succeeded': True
                }
                context_chunks = vector_result.get('context_chunks', [])
                reasoning_chain = graph_result.get('reasoning_chain', [])
                graph_paths = graph_result.get('graph_paths', [])

            elif vector_result:
                # FALLBACK: Only vector succeeded
                logger.warning("Graph agent failed, using vector only",
                              document_id=document_id,
                              graph_error=str(results[1]))
                synthesized_answer = (
                    vector_result['answer'] +
                    "\n\n(Note: Graph analysis unavailable due to processing error)"
                )
                combined_confidence = vector_result['confidence'] * 0.8  # Reduce confidence
                combined_metadata = {
                    'vector_metadata': vector_result.get('metadata', {}),
                    'graph_error': 'Graph agent failed',
                    'degraded_mode': 'vector_only'
                }
                context_chunks = vector_result.get('context_chunks', [])
                reasoning_chain = []
                graph_paths = []

            elif graph_result:
                # FALLBACK: Only graph succeeded
                logger.warning("Vector agent failed, using graph only",
                              document_id=document_id,
                              vector_error=str(results[0]))
                synthesized_answer = (
                    graph_result['answer'] +
                    "\n\n(Note: Vector search unavailable due to processing error)"
                )
                combined_confidence = graph_result['confidence'] * 0.8  # Reduce confidence
                combined_metadata = {
                    'graph_metadata': graph_result.get('metadata', {}),
                    'vector_error': 'Vector agent failed',
                    'degraded_mode': 'graph_only'
                }
                context_chunks = []
                reasoning_chain = graph_result.get('reasoning_chain', [])
                graph_paths = graph_result.get('graph_paths', [])

            else:
                # FAILURE: Both agents failed
                logger.error("Both agents failed in hybrid mode",
                           document_id=document_id,
                           vector_error=str(results[0]),
                           graph_error=str(results[1]))
                raise HTTPException(
                    status_code=500,
                    detail="Unable to process query. Please try again or contact support."
                )

            return QueryResponse(
                answer=synthesized_answer,
                confidence=combined_confidence,
                context_chunks=context_chunks,
                reasoning_chain=reasoning_chain,
                graph_paths=graph_paths,
                metadata=combined_metadata
            )

        else:
            raise HTTPException(
                status_code=500,
                detail=f"Unknown RAG type: {rag_type}"
            )

    except Exception as e:
        logger.error("Query failed", error=str(e), document_id=document_id, exc_info=True)
        # Generic error message (don't leak internal details to user)
        raise HTTPException(
            status_code=500,
            detail="Unable to process query. Please try again or contact support."
        )


async def _synthesize_hybrid_answer(
    question: str,
    vector_answer: str,
    graph_answer: str,
    vector_confidence: float,
    graph_confidence: float
) -> str:
    """
    Synthesize Vector and Graph RAG answers into a unified response.

    WHY SYNTHESIZE?
    ---------------
    Vector RAG might find: "The document mentions X causes Y."
    Graph RAG might find: "X is connected to Y through relationship Z."

    Synthesis combines both perspectives for a richer answer that includes:
    - Factual content (from vector search)
    - Relationship reasoning (from graph traversal)

    APPROACH:
    ---------
    Use LLM to intelligently merge answers, prioritizing the more confident one
    when they conflict, and combining them when they complement each other.

    COST: ~$0.005 per synthesis (small prompt)
    """
    from openai import AsyncOpenAI
    from core.config import settings

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    response = await client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {
                "role": "system",
                "content": """You are an expert at synthesizing information from multiple sources.

You will receive answers from two different retrieval methods:
1. Vector RAG: Semantic similarity search (good for facts)
2. Graph RAG: Relationship reasoning (good for connections)

Your task:
- Combine both answers into one coherent response
- If answers agree, merge them naturally
- If answers differ, weigh by confidence scores
- Preserve key insights from both methods
- Be concise but comprehensive"""
            },
            {
                "role": "user",
                "content": f"""Question: "{question}"

Vector RAG Answer (confidence: {vector_confidence:.2f}):
{vector_answer}

Graph RAG Answer (confidence: {graph_confidence:.2f}):
{graph_answer}

Synthesize these into a single, coherent answer that leverages both perspectives."""
            }
        ],
        temperature=0.3,
        max_tokens=600
    )

    return response.choices[0].message.content