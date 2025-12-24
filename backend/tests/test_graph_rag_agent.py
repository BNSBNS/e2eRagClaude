"""
Test Graph RAG Agent
=====================
Comprehensive tests for the Graph RAG autonomous agent.

Test Coverage:
- Entity extraction from queries
- Node matching in knowledge graph
- Path discovery (1-hop, 2-hop, 3-hop)
- Reasoning chain generation
- End-to-end graph query flow
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.agents.graph_rag_agent import GraphRAGAgent, GraphRAGState


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4jService for testing without database dependency"""
    with patch('services.agents.graph_rag_agent.neo4j_service') as mock:
        # Mock driver.session() to return a context manager
        mock_session = AsyncMock()
        mock.driver.session.return_value.__aenter__.return_value = mock_session
        mock.driver.session.return_value.__aexit__.return_value = None
        yield mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    with patch('services.agents.graph_rag_agent.openai_client') as mock:
        yield mock


class TestEntityExtraction:
    """Test entity extraction from user queries"""

    @pytest.mark.asyncio
    async def test_extracts_single_entity(self, mock_openai_client):
        """Simple queries should extract one entity"""
        agent = GraphRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "entities": ["Einstein"],
            "intent": "find_relationship",
            "max_hops": 2
        }"""
        mock_response.usage.total_tokens = 100
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = GraphRAGState(
            document_id=1,
            user_query="What did Einstein work on?",
            query_entities=[],
            query_intent="",
            matched_nodes=[],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._extract_entities(state)

        assert "Einstein" in result['query_entities']
        assert result['query_intent'] == "find_relationship"
        assert result['max_hops'] == 2

    @pytest.mark.asyncio
    async def test_extracts_multiple_entities_for_comparison(self, mock_openai_client):
        """Comparison queries should extract multiple entities"""
        agent = GraphRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "entities": ["supervised learning", "unsupervised learning"],
            "intent": "compare",
            "max_hops": 2
        }"""
        mock_response.usage.total_tokens = 120
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = GraphRAGState(
            document_id=1,
            user_query="Compare supervised learning and unsupervised learning",
            query_entities=[],
            query_intent="",
            matched_nodes=[],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._extract_entities(state)

        assert len(result['query_entities']) == 2
        assert "supervised learning" in result['query_entities']
        assert "unsupervised learning" in result['query_entities']
        assert result['query_intent'] == "compare"

    @pytest.mark.asyncio
    async def test_sets_appropriate_hop_depth(self, mock_openai_client):
        """Complex multi-hop queries should get deeper traversal"""
        agent = GraphRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = """{
            "entities": ["climate change", "polar bears", "arctic ice"],
            "intent": "causal",
            "max_hops": 3
        }"""
        mock_response.usage.total_tokens = 150
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = GraphRAGState(
            document_id=1,
            user_query="How does climate change affect polar bears through arctic ice?",
            query_entities=[],
            query_intent="",
            matched_nodes=[],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._extract_entities(state)

        assert result['max_hops'] == 3  # Multi-hop reasoning
        assert result['query_intent'] == "causal"


class TestNodeMatching:
    """Test matching query entities to graph nodes"""

    @pytest.mark.asyncio
    async def test_matches_exact_node_name(self, mock_neo4j_service):
        """Should find exact matches in graph"""
        agent = GraphRAGAgent()

        # Mock Neo4j query to return matching node
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [
            {'name': 'Albert Einstein', 'type': 'Person'}
        ]
        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        mock_session.run = AsyncMock(return_value=mock_result)

        state = GraphRAGState(
            document_id=1,
            user_query="What did Einstein do?",
            query_entities=["Einstein"],
            query_intent="find_relationship",
            matched_nodes=[],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._match_nodes(state)

        assert len(result['matched_nodes']) == 1
        assert result['matched_nodes'][0]['name'] == 'Albert Einstein'
        assert result['matched_nodes'][0]['type'] == 'Person'

    @pytest.mark.asyncio
    async def test_handles_no_matches(self, mock_neo4j_service):
        """Should handle gracefully when no nodes match"""
        agent = GraphRAGAgent()

        # Mock empty result
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = []
        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        mock_session.run = AsyncMock(return_value=mock_result)

        state = GraphRAGState(
            document_id=1,
            user_query="What is quantum entanglement?",
            query_entities=["quantum entanglement"],
            query_intent="find_relationship",
            matched_nodes=[],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._match_nodes(state)

        # Should have empty matched_nodes
        assert len(result['matched_nodes']) == 0


class TestPathDiscovery:
    """Test graph traversal and path finding"""

    @pytest.mark.asyncio
    async def test_finds_direct_relationships(self, mock_neo4j_service):
        """Should find 1-hop (direct) relationships"""
        agent = GraphRAGAgent()

        # Mock Neo4j to return 1-hop path
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [
            {
                'node_names': ['Einstein', 'Relativity'],
                'rel_types': ['DEVELOPED'],
                'hops': 1
            }
        ]
        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        mock_session.run = AsyncMock(return_value=mock_result)

        state = GraphRAGState(
            document_id=1,
            user_query="What did Einstein develop?",
            query_entities=["Einstein"],
            query_intent="find_relationship",
            matched_nodes=[{'name': 'Einstein', 'type': 'Person'}],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._discover_paths(state)

        assert len(result['graph_paths']) == 1
        assert result['graph_paths'][0]['hops'] == 1
        assert 'Einstein' in result['graph_paths'][0]['nodes']
        assert 'Relativity' in result['graph_paths'][0]['nodes']
        assert 'DEVELOPED' in result['graph_paths'][0]['relationships']

    @pytest.mark.asyncio
    async def test_finds_multi_hop_paths(self, mock_neo4j_service):
        """Should find 2+ hop (indirect) relationships"""
        agent = GraphRAGAgent()

        # Mock 2-hop path
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [
            {
                'node_names': ['Climate Change', 'Arctic Ice', 'Polar Bears'],
                'rel_types': ['MELTS', 'HABITAT_OF'],
                'hops': 2
            }
        ]
        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        mock_session.run = AsyncMock(return_value=mock_result)

        state = GraphRAGState(
            document_id=1,
            user_query="How does climate change affect polar bears?",
            query_entities=["climate change", "polar bears"],
            query_intent="causal",
            matched_nodes=[
                {'name': 'Climate Change', 'type': 'Concept'},
                {'name': 'Polar Bears', 'type': 'Species'}
            ],
            graph_paths=[],
            max_hops=3,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._discover_paths(state)

        # Should find multi-hop path
        assert len(result['graph_paths']) == 1
        assert result['graph_paths'][0]['hops'] == 2
        assert len(result['graph_paths'][0]['nodes']) == 3
        assert len(result['graph_paths'][0]['relationships']) == 2

    @pytest.mark.asyncio
    async def test_confidence_based_on_paths(self, mock_neo4j_service):
        """Confidence should reflect path quality and quantity"""
        agent = GraphRAGAgent()

        # Mock multiple 1-hop paths (high quality)
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [
            {'node_names': ['A', 'B'], 'rel_types': ['REL1'], 'hops': 1},
            {'node_names': ['A', 'C'], 'rel_types': ['REL2'], 'hops': 1},
            {'node_names': ['A', 'D'], 'rel_types': ['REL3'], 'hops': 1}
        ]
        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        mock_session.run = AsyncMock(return_value=mock_result)

        state = GraphRAGState(
            document_id=1,
            user_query="What is A related to?",
            query_entities=["A"],
            query_intent="find_relationship",
            matched_nodes=[{'name': 'A', 'type': 'Concept'}],
            graph_paths=[],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._discover_paths(state)

        # Confidence should be high (multiple direct paths)
        assert result['confidence'] > 0.5


class TestReasoningGeneration:
    """Test reasoning chain and answer generation"""

    @pytest.mark.asyncio
    async def test_generates_reasoning_chain(self, mock_openai_client):
        """Should explain how entities are connected"""
        agent = GraphRAGAgent()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = """Reasoning:
Einstein developed Relativity, which explains Gravity.

Answer: Einstein's work on Relativity provides the explanation for gravity."""
        mock_response.usage.total_tokens = 200
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        state = GraphRAGState(
            document_id=1,
            user_query="How did Einstein explain gravity?",
            query_entities=["Einstein", "gravity"],
            query_intent="causal",
            matched_nodes=[
                {'name': 'Einstein', 'type': 'Person'},
                {'name': 'Gravity', 'type': 'Concept'}
            ],
            graph_paths=[
                {
                    'nodes': ['Einstein', 'Relativity', 'Gravity'],
                    'relationships': ['DEVELOPED', 'EXPLAINS'],
                    'hops': 2
                }
            ],
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.8,
            total_cost=0.01,
            error_message=""
        )

        result = await agent._generate_reasoning(state)

        # Should have both reasoning and answer
        assert len(result['final_answer']) > 0
        assert len(result['reasoning_chain']) > 0

        # Answer should mention key entities
        full_text = result['final_answer'] + " ".join(result['reasoning_chain'])
        assert "Einstein" in full_text or "Relativity" in full_text

    @pytest.mark.asyncio
    async def test_handles_no_paths(self, mock_openai_client):
        """Should admit when no relationships found"""
        agent = GraphRAGAgent()

        state = GraphRAGState(
            document_id=1,
            user_query="How are X and Y related?",
            query_entities=["X", "Y"],
            query_intent="find_relationship",
            matched_nodes=[],
            graph_paths=[],  # No paths found
            max_hops=2,
            reasoning_chain=[],
            final_answer="",
            confidence=0.0,
            total_cost=0.0,
            error_message=""
        )

        result = await agent._generate_reasoning(state)

        # Should admit inability
        assert "cannot answer" in result['final_answer'].lower() or "no relevant" in result['final_answer'].lower()


class TestEndToEndFlow:
    """Test complete graph RAG workflow"""

    @pytest.mark.asyncio
    async def test_full_query_pipeline(self, mock_neo4j_service, mock_openai_client):
        """Test complete query from start to finish"""
        agent = GraphRAGAgent()

        # Mock OpenAI responses
        def mock_openai_response(messages, **kwargs):
            system_msg = messages[0]['content']

            if "entity extraction" in system_msg.lower():
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="""{
                        "entities": ["Einstein"],
                        "intent": "find_relationship",
                        "max_hops": 2
                    }"""))],
                    usage=MagicMock(total_tokens=100)
                )
            else:  # Reasoning generation
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="Answer: Einstein developed Relativity."))],
                    usage=MagicMock(total_tokens=200)
                )

        mock_openai_client.chat.completions.create = AsyncMock(side_effect=mock_openai_response)

        # Mock Neo4j responses
        mock_node_result = AsyncMock()
        mock_node_result.__aiter__.return_value = [
            {'name': 'Einstein', 'type': 'Person'}
        ]

        mock_path_result = AsyncMock()
        mock_path_result.__aiter__.return_value = [
            {
                'node_names': ['Einstein', 'Relativity'],
                'rel_types': ['DEVELOPED'],
                'hops': 1
            }
        ]

        mock_session = mock_neo4j_service.driver.session.return_value.__aenter__.return_value
        # First call is node matching, second is path discovery
        mock_session.run = AsyncMock(side_effect=[mock_node_result, mock_path_result])

        # Run full query
        result = await agent.query(
            document_id=1,
            user_query="What did Einstein develop?"
        )

        # Verify result structure
        assert 'answer' in result
        assert 'reasoning_chain' in result
        assert 'confidence' in result
        assert 'metadata' in result
        assert 'graph_paths' in result

        # Verify answer exists
        assert len(result['answer']) > 0

        # Verify metadata
        assert result['metadata']['intent'] == 'find_relationship'
        assert result['metadata']['paths_found'] > 0


class TestErrorHandling:
    """Test error resilience"""

    @pytest.mark.asyncio
    async def test_handles_neo4j_failure(self, mock_openai_client):
        """Should handle graph database failures gracefully"""
        agent = GraphRAGAgent()

        # Mock entity extraction to succeed
        mock_openai_client.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="""{
                "entities": ["test"],
                "intent": "find_relationship",
                "max_hops": 2
            }"""))],
            usage=MagicMock(total_tokens=100)
        ))

        # Mock Neo4j to fail
        with patch('services.agents.graph_rag_agent.neo4j_service') as mock_neo4j:
            mock_session = AsyncMock()
            mock_session.run = AsyncMock(side_effect=Exception("Neo4j connection failed"))
            mock_neo4j.driver.session.return_value.__aenter__.return_value = mock_session
            mock_neo4j.driver.session.return_value.__aexit__.return_value = None

            result = await agent.query(
                document_id=1,
                user_query="Test query"
            )

            # Should still return result
            assert 'answer' in result
            # Should have error in metadata
            assert result['metadata'].get('error', '') != ''
