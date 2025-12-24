"""
Test AI Endpoint Routing
=========================
Tests for automatic RAG agent routing based on document type.

Test Coverage:
- Vector RAG routing for VECTOR documents
- Graph RAG routing for GRAPH documents
- Hybrid routing (both agents + synthesis)
- Error handling
- Response format validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from models.document import Document, DocumentStatus, RAGType
from api.ai import query_document, QueryRequest


@pytest.fixture
def mock_vector_document():
    """Mock document processed with vector RAG"""
    doc = MagicMock(spec=Document)
    doc.id = 1
    doc.user_id = 1
    doc.status = DocumentStatus.COMPLETED
    doc.rag_type = RAGType.VECTOR
    doc.filename = "test_vector.pdf"
    return doc


@pytest.fixture
def mock_graph_document():
    """Mock document processed with graph RAG"""
    doc = MagicMock(spec=Document)
    doc.id = 2
    doc.user_id = 1
    doc.status = DocumentStatus.COMPLETED
    doc.rag_type = RAGType.GRAPH
    doc.filename = "test_graph.pdf"
    return doc


@pytest.fixture
def mock_hybrid_document():
    """Mock document processed with hybrid RAG"""
    doc = MagicMock(spec=Document)
    doc.id = 3
    doc.user_id = 1
    doc.status = DocumentStatus.COMPLETED
    doc.rag_type = RAGType.HYBRID
    doc.filename = "test_hybrid.pdf"
    return doc


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.is_active = True
    return user


class TestVectorRouting:
    """Test routing to Vector RAG Agent"""

    @pytest.mark.asyncio
    async def test_routes_vector_document_to_vector_agent(
        self,
        mock_vector_document,
        mock_current_user
    ):
        """VECTOR documents should use Vector RAG Agent"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.vector_rag_agent.query') as mock_vector_agent:

            # Setup mocks
            mock_get_doc.return_value = mock_vector_document
            mock_vector_agent.return_value = {
                'answer': 'This is a vector RAG answer.',
                'confidence': 0.85,
                'context_chunks': [
                    {'text': 'Chunk 1', 'similarity': 0.9},
                    {'text': 'Chunk 2', 'similarity': 0.8}
                ],
                'metadata': {
                    'intent': 'factual_question',
                    'complexity': 'simple',
                    'total_cost_usd': 0.015
                }
            }

            # Create request
            request = QueryRequest(question="What is machine learning?")

            # Execute
            result = await query_document(
                document_id=1,
                request=request,
                current_user=mock_current_user,
                db=None
            )

            # Verify vector agent was called
            mock_vector_agent.assert_called_once_with(
                document_id=1,
                user_query="What is machine learning?"
            )

            # Verify response structure
            assert result.answer == 'This is a vector RAG answer.'
            assert result.confidence == 0.85
            assert len(result.context_chunks) == 2
            assert 'intent' in result.metadata


class TestGraphRouting:
    """Test routing to Graph RAG Agent"""

    @pytest.mark.asyncio
    async def test_routes_graph_document_to_graph_agent(
        self,
        mock_graph_document,
        mock_current_user
    ):
        """GRAPH documents should use Graph RAG Agent"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.graph_rag_agent.query') as mock_graph_agent:

            # Setup mocks
            mock_get_doc.return_value = mock_graph_document
            mock_graph_agent.return_value = {
                'answer': 'Graph reasoning: A connects to B through C.',
                'confidence': 0.75,
                'reasoning_chain': ['A relates to C', 'C connects to B'],
                'graph_paths': [
                    {
                        'nodes': ['A', 'C', 'B'],
                        'relationships': ['RELATES_TO', 'CONNECTS'],
                        'hops': 2
                    }
                ],
                'metadata': {
                    'intent': 'find_relationship',
                    'paths_found': 1,
                    'total_cost_usd': 0.02
                }
            }

            # Create request
            request = QueryRequest(question="How does A relate to B?")

            # Execute
            result = await query_document(
                document_id=2,
                request=request,
                current_user=mock_current_user,
                db=None
            )

            # Verify graph agent was called
            mock_graph_agent.assert_called_once_with(
                document_id=2,
                user_query="How does A relate to B?"
            )

            # Verify response structure
            assert result.answer == 'Graph reasoning: A connects to B through C.'
            assert result.confidence == 0.75
            assert len(result.reasoning_chain) == 2
            assert len(result.graph_paths) == 1
            assert result.graph_paths[0]['hops'] == 2


class TestHybridRouting:
    """Test hybrid mode (both agents)"""

    @pytest.mark.asyncio
    async def test_routes_hybrid_to_both_agents(
        self,
        mock_hybrid_document,
        mock_current_user
    ):
        """HYBRID documents should run both agents and synthesize"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.vector_rag_agent.query') as mock_vector, \
             patch('api.ai.graph_rag_agent.query') as mock_graph, \
             patch('api.ai._synthesize_hybrid_answer') as mock_synthesize:

            # Setup mocks
            mock_get_doc.return_value = mock_hybrid_document

            mock_vector.return_value = {
                'answer': 'Vector answer: ML is AI subset.',
                'confidence': 0.85,
                'context_chunks': [{'text': 'Chunk', 'similarity': 0.9}],
                'metadata': {'cost': 0.01}
            }

            mock_graph.return_value = {
                'answer': 'Graph answer: ML connects to AI via relationships.',
                'confidence': 0.75,
                'reasoning_chain': ['ML relates to AI'],
                'graph_paths': [{'nodes': ['ML', 'AI'], 'relationships': ['SUBSET_OF'], 'hops': 1}],
                'metadata': {'cost': 0.02}
            }

            mock_synthesize.return_value = 'Synthesized: ML is a subset of AI (vector) and they are connected via SUBSET_OF relationship (graph).'

            # Create request
            request = QueryRequest(question="What is machine learning?")

            # Execute
            result = await query_document(
                document_id=3,
                request=request,
                current_user=mock_current_user,
                db=None
            )

            # Verify BOTH agents were called
            mock_vector.assert_called_once()
            mock_graph.assert_called_once()
            mock_synthesize.assert_called_once()

            # Verify synthesis was used
            assert 'Synthesized' in result.answer

            # Verify hybrid response includes both types of data
            assert len(result.context_chunks) > 0  # From vector
            assert len(result.reasoning_chain) > 0  # From graph
            assert len(result.graph_paths) > 0  # From graph

            # Verify metadata includes both
            assert 'vector_metadata' in result.metadata
            assert 'graph_metadata' in result.metadata


class TestErrorHandling:
    """Test error cases and validation"""

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_document(self, mock_current_user):
        """Should return 404 for documents that don't exist"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc:
            mock_get_doc.return_value = None

            request = QueryRequest(question="Test question")

            with pytest.raises(HTTPException) as exc_info:
                await query_document(
                    document_id=999,
                    request=request,
                    current_user=mock_current_user,
                    db=None
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_rejects_processing_documents(self, mock_current_user):
        """Should reject documents still being processed"""

        processing_doc = MagicMock(spec=Document)
        processing_doc.status = DocumentStatus.PROCESSING
        processing_doc.rag_type = RAGType.VECTOR

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc:
            mock_get_doc.return_value = processing_doc

            request = QueryRequest(question="Test question")

            with pytest.raises(HTTPException) as exc_info:
                await query_document(
                    document_id=1,
                    request=request,
                    current_user=mock_current_user,
                    db=None
                )

            assert exc_info.value.status_code == 400
            assert "not ready" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_handles_agent_failure_gracefully(
        self,
        mock_vector_document,
        mock_current_user
    ):
        """Should handle agent failures with proper error response"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.vector_rag_agent.query') as mock_vector:

            mock_get_doc.return_value = mock_vector_document
            mock_vector.side_effect = Exception("Agent processing failed")

            request = QueryRequest(question="Test question")

            with pytest.raises(HTTPException) as exc_info:
                await query_document(
                    document_id=1,
                    request=request,
                    current_user=mock_current_user,
                    db=None
                )

            assert exc_info.value.status_code == 500
            assert "failed" in exc_info.value.detail.lower()


class TestBackwardCompatibility:
    """Test handling of documents without rag_type (backward compatibility)"""

    @pytest.mark.asyncio
    async def test_defaults_to_vector_for_null_rag_type(self, mock_current_user):
        """Documents with null rag_type should default to VECTOR"""

        old_doc = MagicMock(spec=Document)
        old_doc.id = 10
        old_doc.status = DocumentStatus.COMPLETED
        old_doc.rag_type = None  # Old document without rag_type

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.vector_rag_agent.query') as mock_vector:

            mock_get_doc.return_value = old_doc
            mock_vector.return_value = {
                'answer': 'Answer',
                'confidence': 0.8,
                'context_chunks': [],
                'metadata': {}
            }

            request = QueryRequest(question="Test")

            result = await query_document(
                document_id=10,
                request=request,
                current_user=mock_current_user,
                db=None
            )

            # Should have called vector agent (default)
            mock_vector.assert_called_once()
            assert result.answer == 'Answer'


class TestResponseFormat:
    """Test response format consistency"""

    @pytest.mark.asyncio
    async def test_vector_response_has_all_fields(
        self,
        mock_vector_document,
        mock_current_user
    ):
        """Vector response should have all expected fields"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.vector_rag_agent.query') as mock_vector:

            mock_get_doc.return_value = mock_vector_document
            mock_vector.return_value = {
                'answer': 'Answer',
                'confidence': 0.85,
                'context_chunks': [{'text': 'chunk', 'similarity': 0.9}],
                'metadata': {'intent': 'test'}
            }

            request = QueryRequest(question="Test")
            result = await query_document(1, request, mock_current_user, None)

            # Check all fields
            assert hasattr(result, 'answer')
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'context_chunks')
            assert hasattr(result, 'reasoning_chain')  # May be empty
            assert hasattr(result, 'graph_paths')  # May be empty
            assert hasattr(result, 'metadata')

    @pytest.mark.asyncio
    async def test_graph_response_has_all_fields(
        self,
        mock_graph_document,
        mock_current_user
    ):
        """Graph response should have all expected fields"""

        with patch('api.ai.DocumentService.get_document_by_id') as mock_get_doc, \
             patch('api.ai.graph_rag_agent.query') as mock_graph:

            mock_get_doc.return_value = mock_graph_document
            mock_graph.return_value = {
                'answer': 'Graph answer',
                'confidence': 0.75,
                'reasoning_chain': ['step1'],
                'graph_paths': [{'nodes': ['A', 'B'], 'relationships': ['REL'], 'hops': 1}],
                'metadata': {'paths_found': 1}
            }

            request = QueryRequest(question="Test")
            result = await query_document(2, request, mock_current_user, None)

            # Check all fields
            assert result.answer == 'Graph answer'
            assert result.confidence == 0.75
            assert len(result.reasoning_chain) > 0
            assert len(result.graph_paths) > 0
            assert result.metadata['paths_found'] == 1
