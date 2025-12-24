"""
Vector RAG Agent
=================
Specialized autonomous agent for vector-based retrieval-augmented generation.

This agent uses LangGraph state machines to implement a multi-step RAG pipeline:
1. Query Analysis: Understand user intent and extract key concepts
2. Adaptive Retrieval: Perform similarity search with dynamic parameters
3. Reranking: Use LLM to judge relevance and filter noise
4. Answer Generation: Synthesize final answer with source citations

WHY THIS APPROACH?
------------------
- Query Analysis: Improves retrieval by understanding intent (e.g., "compare X and Y"
  requires retrieving both concepts, not just similarity to the full query)
- Adaptive Retrieval: Simple queries need fewer chunks (faster), complex ones need more
- Reranking: Vector similarity doesn't always capture semantic relevance perfectly
- Citations: Essential for trust and verification

WHEN TO USE VECTOR RAG:
-----------------------
✓ Q&A: "What is X?", "How does Y work?"
✓ Fact finding: "What date did Z happen?"
✓ Semantic similarity: "Find content similar to X"
✓ Fast retrieval: Millisecond-level search

✗ NOT ideal for relationship reasoning ("How does X affect Y?")
✗ NOT ideal for multi-hop questions ("If A then B, what about C?")
  (Use Graph RAG for those)

EDUCATIONAL NOTES:
------------------
Embeddings: Text → numerical vectors (e.g., "dog" → [0.2, 0.8, ...])
Cosine Similarity: Measures angle between vectors (0=unrelated, 1=identical)
Trade-offs: More chunks = better coverage but slower + more expensive
"""

from typing import TypedDict, List, Dict, Annotated
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI
from services.vector_store import VectorStore
from core.config import settings
import structlog
import json

logger = structlog.get_logger()

# Initialize OpenAI client for LLM calls
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class VectorRAGState(TypedDict):
    """
    State that flows through the Vector RAG pipeline.

    Each step reads from and writes to this shared state object.
    LangGraph automatically passes this between nodes.
    """
    # Input
    document_id: int
    user_query: str

    # Query Analysis Results
    query_intent: str          # e.g., "factual_question", "comparison", "summary"
    query_complexity: str      # "simple", "moderate", "complex"
    key_concepts: List[str]    # Main entities/concepts to search for

    # Retrieval Results
    n_results: int             # Adaptive: 3-8 based on complexity
    retrieved_chunks: List[Dict]  # Raw chunks from vector search

    # Reranking Results
    reranked_chunks: List[Dict]   # Filtered to most relevant

    # Final Output
    final_answer: str
    sources: List[int]         # Chunk indices used in answer
    confidence: float          # 0.0-1.0 based on retrieval quality

    # Metadata
    total_cost: float
    error_message: str


class VectorRAGAgent:
    """
    Autonomous Vector RAG agent using LangGraph.

    This agent orchestrates a sophisticated RAG pipeline that adapts
    to query complexity and provides high-quality, cited answers.
    """

    def __init__(self):
        """Build the state machine workflow"""
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build the Vector RAG state machine.

        Flow: analyze_query → retrieve_chunks → rerank_chunks → generate_answer

        Each node is a function that takes state and returns updated state.
        LangGraph handles state passing and execution order.
        """
        workflow = StateGraph(VectorRAGState)

        # Add processing nodes
        workflow.add_node("analyze_query", self._analyze_query)
        workflow.add_node("retrieve_chunks", self._retrieve_chunks)
        workflow.add_node("rerank_chunks", self._rerank_chunks)
        workflow.add_node("generate_answer", self._generate_answer)

        # Define linear flow (could add conditional edges for more sophistication)
        workflow.add_edge("analyze_query", "retrieve_chunks")
        workflow.add_edge("retrieve_chunks", "rerank_chunks")
        workflow.add_edge("rerank_chunks", "generate_answer")
        workflow.add_edge("generate_answer", END)

        # Set entry point
        workflow.set_entry_point("analyze_query")

        return workflow.compile()

    async def _analyze_query(self, state: VectorRAGState) -> VectorRAGState:
        """
        Step 1: Analyze the user query to understand intent and complexity.

        WHY THIS STEP?
        --------------
        A query like "Compare X and Y" needs BOTH X and Y chunks.
        Simple similarity search might only retrieve X-related chunks.

        By understanding intent first, we can:
        - Extract key concepts to search for separately
        - Determine how many results we need (simple Q needs fewer chunks)
        - Choose the right generation strategy (factual vs analytical)

        COST: ~$0.001 per query (GPT-4 with structured output)
        """
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a query analysis expert. Analyze user queries to optimize retrieval.

Classify queries into:
- Intent: "factual_question", "comparison", "summary", "how_to", "definition"
- Complexity: "simple" (1 concept), "moderate" (2-3 concepts), "complex" (4+ concepts or multi-step)
- Key concepts: Main entities/topics to retrieve information about"""
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this query:
"{state['user_query']}"

Respond in JSON:
{{
    "intent": "factual_question|comparison|summary|how_to|definition",
    "complexity": "simple|moderate|complex",
    "key_concepts": ["concept1", "concept2", ...]
}}"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1  # Low temperature for consistent analysis
            )

            analysis = json.loads(response.choices[0].message.content)

            # Update state with analysis
            state['query_intent'] = analysis.get('intent', 'factual_question')
            state['query_complexity'] = analysis.get('complexity', 'simple')
            state['key_concepts'] = analysis.get('key_concepts', [])

            # Adaptive retrieval: More complex queries need more chunks
            # Simple: 3 chunks (fast, cheap)
            # Moderate: 5 chunks (balanced)
            # Complex: 8 chunks (comprehensive)
            complexity_to_chunks = {
                'simple': 3,
                'moderate': 5,
                'complex': 8
            }
            state['n_results'] = complexity_to_chunks.get(
                state['query_complexity'],
                5  # Default fallback
            )

            # Track cost (GPT-4 turbo: ~$0.01/1K input, ~$0.03/1K output)
            tokens_used = response.usage.total_tokens
            state['total_cost'] = (tokens_used / 1000) * 0.02

            logger.info(
                "Query analyzed",
                intent=state['query_intent'],
                complexity=state['query_complexity'],
                concepts=state['key_concepts'],
                will_retrieve=state['n_results']
            )

            return state

        except Exception as e:
            logger.error("Query analysis failed", error=str(e))
            state['error_message'] = f"Analysis failed: {str(e)}"
            # Set defaults to continue pipeline
            state['query_intent'] = 'factual_question'
            state['query_complexity'] = 'simple'
            state['key_concepts'] = []
            state['n_results'] = 5
            return state

    async def _retrieve_chunks(self, state: VectorRAGState) -> VectorRAGState:
        """
        Step 2: Retrieve relevant document chunks using vector similarity search.

        HOW VECTOR SEARCH WORKS:
        ------------------------
        1. User query → Embedding model → Query vector [0.2, 0.8, -0.1, ...]
        2. Compare query vector to all document chunk vectors using cosine similarity
        3. Return top N most similar chunks (highest cosine similarity scores)

        COSINE SIMILARITY:
        ------------------
        Measures the angle between two vectors:
        - 1.0 = identical direction (perfect match)
        - 0.0 = perpendicular (unrelated)
        - -1.0 = opposite direction (contradictory, rare in embeddings)

        ChromaDB uses HNSW (Hierarchical Navigable Small World) index for fast search.
        Search time: O(log N) instead of O(N) - critical for large document collections.

        COST: Embedding query costs ~$0.0001 (OpenAI ada-002)
        """
        try:
            # Perform vector similarity search
            search_results = await VectorStore.similarity_search(
                document_id=state['document_id'],
                query=state['user_query'],
                n_results=state['n_results']
            )

            # Format results with metadata
            state['retrieved_chunks'] = [
                {
                    'text': chunk,
                    'distance': distance,  # Lower = more similar (cosine distance)
                    'similarity': 1 - distance,  # Convert to similarity score
                    'metadata': meta,
                    'chunk_index': i
                }
                for i, (chunk, distance, meta) in enumerate(zip(
                    search_results['chunks'],
                    search_results['distances'],
                    search_results['metadatas']
                ))
            ]

            # Calculate average similarity for confidence metric
            if state['retrieved_chunks']:
                avg_similarity = sum(c['similarity'] for c in state['retrieved_chunks']) / len(state['retrieved_chunks'])
                state['confidence'] = min(avg_similarity, 1.0)  # Clamp to [0, 1]
            else:
                state['confidence'] = 0.0

            logger.info(
                "Chunks retrieved",
                count=len(state['retrieved_chunks']),
                avg_similarity=round(state['confidence'], 3)
            )

            return state

        except Exception as e:
            logger.error("Retrieval failed", error=str(e))
            state['error_message'] = f"Retrieval failed: {str(e)}"
            state['retrieved_chunks'] = []
            state['confidence'] = 0.0
            return state

    async def _rerank_chunks(self, state: VectorRAGState) -> VectorRAGState:
        """
        Step 3: Rerank chunks using LLM to judge actual relevance.

        WHY RERANKING?
        --------------
        Vector similarity has limitations:
        - "Bank" (financial) vs "Bank" (river) → High vector similarity but different meaning
        - Keyword matches without semantic relevance
        - Chunks that mention concepts but don't answer the question

        LLM reranking evaluates actual usefulness for answering the specific question.

        TRADE-OFF:
        ----------
        Cost: Each reranking call costs ~$0.002-0.005
        Benefit: Removes 20-40% of irrelevant chunks, improving answer quality

        For production at scale: Consider using a smaller reranking model (e.g., cross-encoders)
        or skip reranking for simple queries to reduce costs.
        """
        if not state['retrieved_chunks']:
            state['reranked_chunks'] = []
            return state

        try:
            # Prepare chunks for evaluation
            chunks_text = "\n\n".join([
                f"[Chunk {i}]: {chunk['text'][:300]}..."  # Truncate for cost savings
                for i, chunk in enumerate(state['retrieved_chunks'])
            ])

            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a relevance judge. Evaluate which chunks are useful for answering the query.

Return ONLY the indices of relevant chunks (e.g., [0, 2, 4]).
A chunk is relevant if it contains information that helps answer the question.
Irrelevant chunks: mentions keywords but doesn't address the query."""
                    },
                    {
                        "role": "user",
                        "content": f"""Query: "{state['user_query']}"

Retrieved chunks:
{chunks_text}

Which chunk indices are relevant? Respond with JSON:
{{"relevant_indices": [0, 1, ...]}}"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            relevance = json.loads(response.choices[0].message.content)
            relevant_indices = set(relevance.get('relevant_indices', []))

            # Filter chunks to only relevant ones
            state['reranked_chunks'] = [
                chunk for i, chunk in enumerate(state['retrieved_chunks'])
                if i in relevant_indices
            ]

            # Update cost
            tokens_used = response.usage.total_tokens
            state['total_cost'] += (tokens_used / 1000) * 0.02

            # Adjust confidence based on reranking
            if state['retrieved_chunks']:
                retention_rate = len(state['reranked_chunks']) / len(state['retrieved_chunks'])
                state['confidence'] *= retention_rate  # Lower confidence if many chunks filtered out

            logger.info(
                "Chunks reranked",
                original=len(state['retrieved_chunks']),
                kept=len(state['reranked_chunks']),
                filtered_out=len(state['retrieved_chunks']) - len(state['reranked_chunks'])
            )

            return state

        except Exception as e:
            logger.error("Reranking failed, using all chunks", error=str(e))
            # Fallback: use all retrieved chunks if reranking fails
            state['reranked_chunks'] = state['retrieved_chunks']
            return state

    async def _generate_answer(self, state: VectorRAGState) -> VectorRAGState:
        """
        Step 4: Generate final answer using reranked chunks as context.

        RAG PROMPT ENGINEERING:
        -----------------------
        Key principles:
        1. Explicit context boundaries: "Use ONLY information from context"
        2. Hallucination prevention: "If not in context, say 'I cannot find...'"
        3. Source attribution: "Cite chunk numbers"
        4. Temperature: 0.3 (low but not zero for natural language)

        COST: This is the most expensive step (~$0.01-0.05 per answer depending on context size)

        OUTPUT FORMAT:
        --------------
        Answer includes:
        - Clear, direct response to question
        - Citations [Chunk X] for verification
        - Admission when information is not available
        """
        if not state['reranked_chunks']:
            state['final_answer'] = "I cannot answer this question as no relevant information was found in the document."
            state['sources'] = []
            return state

        try:
            # Construct context from reranked chunks
            context_parts = []
            for i, chunk in enumerate(state['reranked_chunks']):
                context_parts.append(f"[Source {i+1}]:\n{chunk['text']}")

            context = "\n\n".join(context_parts)

            # Generate answer with strict grounding
            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,  # GPT-4 for quality
                messages=[
                    {
                        "role": "system",
                        "content": """You are a precise assistant that answers questions using ONLY the provided context.

Rules:
1. Answer ONLY based on the context provided
2. Cite sources using [Source N] notation
3. If the answer is not in the context, say "I cannot find this information in the document"
4. Be concise but complete
5. Do not add external knowledge"""
                    },
                    {
                        "role": "user",
                        "content": f"""Context:
{context}

Question: {state['user_query']}

Answer the question using only the context above. Cite your sources."""
                    }
                ],
                temperature=0.3,  # Low temp for factual accuracy, but not 0 for natural language
                max_tokens=500
            )

            state['final_answer'] = response.choices[0].message.content

            # Extract which sources were used (parse [Source N] from answer)
            import re
            source_mentions = re.findall(r'\[Source (\d+)\]', state['final_answer'])
            state['sources'] = [int(s) - 1 for s in source_mentions]  # Convert to 0-indexed

            # Final cost calculation
            tokens_used = response.usage.total_tokens
            state['total_cost'] += (tokens_used / 1000) * 0.03  # GPT-4 output tokens

            logger.info(
                "Answer generated",
                length=len(state['final_answer']),
                sources_cited=len(state['sources']),
                total_cost_usd=round(state['total_cost'], 4)
            )

            return state

        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            state['error_message'] = f"Generation failed: {str(e)}"
            state['final_answer'] = f"Error generating answer: {str(e)}"
            state['sources'] = []
            return state

    async def query(
        self,
        document_id: int,
        user_query: str
    ) -> Dict:
        """
        Execute the full Vector RAG pipeline.

        Args:
            document_id: ID of the document to query
            user_query: User's natural language question

        Returns:
            Dict containing:
            - answer: Generated response with citations
            - confidence: 0.0-1.0 quality score
            - sources: List of chunk indices used
            - metadata: Cost, token usage, processing steps

        Example:
            result = await agent.query(
                document_id=123,
                user_query="What is machine learning?"
            )
            print(result['answer'])
            # "Machine learning is... [Source 1] [Source 3]"
        """
        # Initialize state
        initial_state = VectorRAGState(
            document_id=document_id,
            user_query=user_query,
            query_intent="",
            query_complexity="",
            key_concepts=[],
            n_results=5,
            retrieved_chunks=[],
            reranked_chunks=[],
            final_answer="",
            sources=[],
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        # Run through the state machine
        final_state = await self.workflow.ainvoke(initial_state)

        # Format response
        return {
            'answer': final_state['final_answer'],
            'confidence': round(final_state['confidence'], 3),
            'sources': final_state['sources'],
            'metadata': {
                'intent': final_state['query_intent'],
                'complexity': final_state['query_complexity'],
                'key_concepts': final_state['key_concepts'],
                'chunks_retrieved': len(final_state['retrieved_chunks']),
                'chunks_used': len(final_state['reranked_chunks']),
                'total_cost_usd': round(final_state['total_cost'], 4),
                'error': final_state.get('error_message', '')
            },
            # Include actual chunks for verification/debugging
            'context_chunks': [
                {
                    'text': chunk['text'],
                    'similarity': round(chunk['similarity'], 3)
                }
                for chunk in final_state['reranked_chunks']
            ]
        }


# Global instance for easy import
vector_rag_agent = VectorRAGAgent()
