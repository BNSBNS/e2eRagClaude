"""
Test Vector RAG Agent
======================
Comprehensive tests for the Vector RAG autonomous agent.

Test Coverage:
- Query analysis (intent detection, complexity classification)
- Adaptive retrieval (varying chunk counts based on complexity)
- Reranking (filtering irrelevant chunks)
- Answer generation (citations, accuracy)
- End-to-end query flow
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.agents.vector_rag_agent import VectorRAGAgent, VectorRAGState


@pytest.fixture
def sample_document_chunks():
    """Sample document chunks for testing retrieval"""
    return [
        "Machine learning is a subset of artificial intelligence that focuses on learning from data.",
        "Neural networks are computational models inspired by biological neural networks in the brain.",
        "Deep learning uses multi-layer neural networks to learn hierarchical representations.",
        "Supervised learning requires labeled training data with input-output pairs.",
        "Unsupervised learning discovers patterns in data without explicit labels."
    ]


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for testing without ChromaDB dependency"""
    with patch('services.agents.vector_rag_agent.VectorStore') as mock:
        # Mock similarity_search to return sample results
        mock.similarity_search = AsyncMock(return_value={
            'chunks': [
                "Machine learning is a subset of artificial intelligence.",
                "Neural networks are computational models.",
                "Deep learning uses multi-layer neural networks."
            ],
            'distances': [0.1, 0.2, 0.3],  # Lower = more similar
            'metadatas': [
                {'chunk_index': 0},
                {'chunk_index': 1},
                {'chunk_index': 2}
            ]
        })
        yield mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client to avoid API calls during tests"""
    with patch('services.agents.vector_rag_agent.openai_client') as mock:
        yield mock


class TestQueryAnalysis:
    """Test the query analysis step"""

    @pytest.mark.asyncio
    async def test_simple_query_classification(self, mock_openai_client):
        """Simple queries should be classified as 'simple' complexity"""
        agent = VectorRAGAgent()

        # Mock OpenAI response for query analysis
        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "intent": "factual_question",
            "complexity": "simple",
            "key_concepts": ["machine learning"]
        }"""
        mock_response.usage.total_tokens = 100
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = VectorRAGState(
            document_id=1,
            user_query="What is machine learning?",
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

        result = await agent._analyze_query(state)

        assert result['query_intent'] == "factual_question"
        assert result['query_complexity'] == "simple"
        assert "machine learning" in result['key_concepts']
        assert result['n_results'] == 3  # Simple queries get 3 chunks

    @pytest.mark.asyncio
    async def test_complex_query_classification(self, mock_openai_client):
        """Complex queries should get more retrieval chunks"""
        agent = VectorRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "intent": "comparison",
            "complexity": "complex",
            "key_concepts": ["supervised learning", "unsupervised learning", "neural networks", "deep learning"]
        }"""
        mock_response.usage.total_tokens = 150
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = VectorRAGState(
            document_id=1,
            user_query="Compare supervised and unsupervised learning in the context of neural networks and deep learning",
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

        result = await agent._analyze_query(state)

        assert result['query_intent'] == "comparison"
        assert result['query_complexity'] == "complex"
        assert result['n_results'] == 8  # Complex queries get 8 chunks
        assert len(result['key_concepts']) >= 2


class TestRetrievalAndRanking:
    """Test retrieval and reranking steps"""

    @pytest.mark.asyncio
    async def test_retrieval_calculates_confidence(self, mock_vector_store):
        """Retrieval should calculate confidence based on similarity scores"""
        agent = VectorRAGAgent()

        state = VectorRAGState(
            document_id=1,
            user_query="What is machine learning?",
            query_intent="factual_question",
            query_complexity="simple",
            key_concepts=["machine learning"],
            n_results=3,
            retrieved_chunks=[],
            reranked_chunks=[],
            final_answer="",
            sources=[],
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._retrieve_chunks(state)

        # Should have retrieved chunks
        assert len(result['retrieved_chunks']) == 3

        # Confidence should be high (similarity = 1 - distance)
        # With distances [0.1, 0.2, 0.3], avg similarity = 0.8
        assert result['confidence'] > 0.7
        assert result['confidence'] <= 1.0

        # Each chunk should have metadata
        for chunk in result['retrieved_chunks']:
            assert 'text' in chunk
            assert 'similarity' in chunk
            assert 'distance' in chunk

    @pytest.mark.asyncio
    async def test_reranking_filters_irrelevant(self, mock_openai_client):
        """Reranking should filter out irrelevant chunks"""
        agent = VectorRAGAgent()

        # Mock OpenAI to say only chunks 0 and 2 are relevant
        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "relevant_indices": [0, 2]
        }"""
        mock_response.usage.total_tokens = 200
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = VectorRAGState(
            document_id=1,
            user_query="What is machine learning?",
            query_intent="factual_question",
            query_complexity="simple",
            key_concepts=["machine learning"],
            n_results=3,
            retrieved_chunks=[
                {'text': 'Chunk 0 about ML', 'similarity': 0.9},
                {'text': 'Chunk 1 unrelated', 'similarity': 0.7},
                {'text': 'Chunk 2 about ML', 'similarity': 0.85}
            ],
            reranked_chunks=[],
            final_answer="",
            sources=[],
            confidence=0.9,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._rerank_chunks(state)

        # Should keep only chunks 0 and 2
        assert len(result['reranked_chunks']) == 2
        assert result['reranked_chunks'][0]['text'] == 'Chunk 0 about ML'
        assert result['reranked_chunks'][1]['text'] == 'Chunk 2 about ML'

        # Confidence should be adjusted (2/3 retention = 0.67 multiplier)
        assert result['confidence'] < 0.9


class TestAnswerGeneration:
    """Test answer generation step"""

    @pytest.mark.asyncio
    async def test_generates_answer_with_citations(self, mock_openai_client):
        """Answer should include source citations"""
        agent = VectorRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Machine learning is a subset of AI that learns from data [Source 1]."
        mock_response.usage.total_tokens = 300
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = VectorRAGState(
            document_id=1,
            user_query="What is machine learning?",
            query_intent="factual_question",
            query_complexity="simple",
            key_concepts=["machine learning"],
            n_results=3,
            retrieved_chunks=[],
            reranked_chunks=[
                {'text': 'Machine learning is a subset of AI.', 'similarity': 0.9}
            ],
            final_answer="",
            sources=[],
            confidence=0.9,
            total_cost=0.01,
            error_message=""
        )

        result = await agent._generate_answer(state)

        # Should have generated an answer
        assert len(result['final_answer']) > 0
        assert '[Source 1]' in result['final_answer']

        # Should track which sources were cited
        assert 0 in result['sources']  # Source 1 → index 0

    @pytest.mark.asyncio
    async def test_handles_no_chunks_gracefully(self, mock_openai_client):
        """Should return appropriate message when no chunks available"""
        agent = VectorRAGAgent()

        state = VectorRAGState(
            document_id=1,
            user_query="What is quantum computing?",
            query_intent="factual_question",
            query_complexity="simple",
            key_concepts=["quantum computing"],
            n_results=3,
            retrieved_chunks=[],
            reranked_chunks=[],  # No chunks
            final_answer="",
            sources=[],
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._generate_answer(state)

        # Should admit inability to answer
        assert "cannot answer" in result['final_answer'].lower()
        assert len(result['sources']) == 0


class TestEndToEndFlow:
    """Test the complete agent workflow"""

    @pytest.mark.asyncio
    async def test_full_query_pipeline(self, mock_vector_store, mock_openai_client):
        """Test complete query from start to finish"""
        agent = VectorRAGAgent()

        # Mock all OpenAI calls
        def mock_openai_response(messages, **kwargs):
            # Determine which step based on system message
            system_msg = messages[0]['content']

            if "query analysis" in system_msg.lower():
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="""{
                        "intent": "factual_question",
                        "complexity": "simple",
                        "key_concepts": ["machine learning"]
                    }"""))],
                    usage=MagicMock(total_tokens=100)
                )
            elif "relevance judge" in system_msg.lower():
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="""{
                        "relevant_indices": [0, 1, 2]
                    }"""))],
                    usage=MagicMock(total_tokens=150)
                )
            else:  # Answer generation
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="Machine learning is a subset of AI [Source 1]."))],
                    usage=MagicMock(total_tokens=200)
                )

        mock_openai_client.chat.completions.create = AsyncMock(side_effect=mock_openai_response)

        # Run full query
        result = await agent.query(
            document_id=1,
            user_query="What is machine learning?"
        )

        # Verify result structure
        assert 'answer' in result
        assert 'confidence' in result
        assert 'sources' in result
        assert 'metadata' in result
        assert 'context_chunks' in result

        # Verify answer quality
        assert len(result['answer']) > 0
        assert result['confidence'] > 0.0

        # Verify metadata
        assert result['metadata']['intent'] == 'factual_question'
        assert result['metadata']['complexity'] == 'simple'
        assert result['metadata']['total_cost_usd'] > 0


class TestErrorHandling:
    """Test error handling and resilience"""

    @pytest.mark.asyncio
    async def test_handles_openai_failure_gracefully(self, mock_vector_store):
        """Should handle OpenAI API failures without crashing"""
        agent = VectorRAGAgent()

        with patch('services.agents.vector_rag_agent.openai_client') as mock_client:
            # Simulate API failure
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            result = await agent.query(
                document_id=1,
                user_query="What is machine learning?"
            )

            # Should still return a result (with error message)
            assert 'answer' in result
            assert 'metadata' in result
            # Error should be logged in metadata
            assert result['metadata'].get('error', '') != ''

    @pytest.mark.asyncio
    async def test_handles_vector_store_failure(self, mock_openai_client):
        """Should handle vector store failures"""
        agent = VectorRAGAgent()

        with patch('services.agents.vector_rag_agent.VectorStore') as mock_vs:
            mock_vs.similarity_search = AsyncMock(side_effect=Exception("ChromaDB connection failed"))

            # Mock query analysis to succeed
            mock_openai_client.chat.completions.create = AsyncMock(return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="""{
                    "intent": "factual_question",
                    "complexity": "simple",
                    "key_concepts": ["ML"]
                }"""))],
                usage=MagicMock(total_tokens=100)
            ))

            result = await agent.query(
                document_id=1,
                user_query="What is ML?"
            )

            # Should still complete (with degraded results)
            assert 'answer' in result
            # Confidence should be very low or zero
            assert result['confidence'] == 0.0
