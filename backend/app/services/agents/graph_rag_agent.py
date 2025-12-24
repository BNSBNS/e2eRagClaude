"""
Graph RAG Agent
===============
Specialized autonomous agent for graph-based retrieval-augmented generation.

This agent uses LangGraph state machines to implement knowledge graph reasoning:
1. Entity Extraction: Extract key entities from the user query
2. Node Matching: Find corresponding nodes in the Neo4j knowledge graph
3. Path Discovery: Traverse relationships to find connections (1-3 hops)
4. Reasoning: Generate answer explaining relationship chains

WHY THIS APPROACH?
------------------
- Entity Extraction: Map natural language to graph nodes precisely
- Path Discovery: Uncover indirect relationships that vector search misses
- Multi-hop Reasoning: Answer "how" and "why" by connecting multiple relationships
- Explainable: Can show the exact relationship chain that led to the answer

WHEN TO USE GRAPH RAG:
----------------------
✓ Relationship questions: "How does X affect Y?", "What connects A and B?"
✓ Multi-hop reasoning: "If A causes B, and B causes C, what about D?"
✓ Comparison questions: "What do X and Y have in common?"
✓ Structural questions: "What are the dependencies of X?"
✓ Causal reasoning: "Why did X happen?"

✗ NOT ideal for simple fact lookup ("What is X?")
✗ NOT ideal for semantic similarity ("Find content like X")
  (Use Vector RAG for those)

EDUCATIONAL NOTES:
------------------
Knowledge Graph: Nodes (entities) connected by edges (relationships)
Example: (Person:Alice)-[:WORKS_AT]->(Company:TechCorp)

Graph Traversal: Walking along edges to find paths
- 1-hop: Direct relationships (A→B)
- 2-hop: Indirect relationships (A→B→C)
- 3-hop: Multi-step reasoning (A→B→C→D)

Cypher: Neo4j's query language (like SQL for graphs)
Pattern matching: MATCH (a)-[:REL]->(b) WHERE a.name = "X"

Trade-offs:
+ Discovers hidden connections
+ Explainable reasoning
- Slower than vector search (graph traversal vs vector lookup)
- Requires quality entity extraction
"""

from typing import TypedDict, List, Dict, Annotated
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI
from services.neo4j_service import neo4j_service
from core.config import settings
import structlog
import json

logger = structlog.get_logger()

# Initialize OpenAI client for LLM calls
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class GraphRAGState(TypedDict):
    """
    State that flows through the Graph RAG pipeline.

    Each step reads from and writes to this shared state object.
    LangGraph automatically passes this between nodes.
    """
    # Input
    document_id: int
    user_query: str

    # Entity Extraction Results
    query_entities: List[str]      # Entities mentioned in query
    query_intent: str               # "find_relationship", "explain_connection", etc.

    # Graph Matching Results
    matched_nodes: List[Dict]       # Nodes found in graph matching query entities

    # Path Discovery Results
    graph_paths: List[Dict]         # Relationship paths found in graph
    max_hops: int                   # How far to traverse (1-3)

    # Reasoning Results
    reasoning_chain: List[str]      # Step-by-step explanation
    final_answer: str
    confidence: float               # Based on path relevance

    # Metadata
    total_cost: float
    error_message: str


class GraphRAGAgent:
    """
    Autonomous Graph RAG agent using LangGraph.

    This agent orchestrates knowledge graph traversal and reasoning
    to answer questions that require understanding relationships.
    """

    def __init__(self):
        """Build the state machine workflow"""
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build the Graph RAG state machine.

        Flow: extract_entities → match_nodes → discover_paths → generate_reasoning

        Each node is a function that takes state and returns updated state.
        LangGraph handles state passing and execution order.
        """
        workflow = StateGraph(GraphRAGState)

        # Add processing nodes
        workflow.add_node("extract_entities", self._extract_entities)
        workflow.add_node("match_nodes", self._match_nodes)
        workflow.add_node("discover_paths", self._discover_paths)
        workflow.add_node("generate_reasoning", self._generate_reasoning)

        # Define linear flow
        workflow.add_edge("extract_entities", "match_nodes")
        workflow.add_edge("match_nodes", "discover_paths")
        workflow.add_edge("discover_paths", "generate_reasoning")
        workflow.add_edge("generate_reasoning", END)

        # Set entry point
        workflow.set_entry_point("extract_entities")

        return workflow.compile()

    async def _extract_entities(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 1: Extract entities and understand query intent.

        WHY THIS STEP?
        --------------
        Natural language queries mention entities in various forms:
        - "How does climate change affect polar bears?" → ["climate change", "polar bears"]
        - "What's the connection between AI and job automation?" → ["AI", "job automation"]

        We need to:
        1. Identify which parts of the query are entities
        2. Understand what kind of relationship question is being asked
        3. Determine traversal depth (direct vs multi-hop)

        COST: ~$0.001 per query (GPT-4 with structured output)
        """
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an entity extraction expert for knowledge graphs.

Extract entities and classify relationship queries:
- Entities: Key concepts, names, topics mentioned
- Intent: Type of relationship question being asked
  * "find_relationship": "How does X relate to Y?"
  * "explain_connection": "What connects X and Y?"
  * "compare": "What do X and Y have in common?"
  * "causal": "Why/How does X affect Y?"
  * "structural": "What depends on X?"
- Hops needed: 1 (direct), 2 (one intermediate), 3 (complex multi-step)"""
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this query:
"{state['user_query']}"

Respond in JSON:
{{
    "entities": ["entity1", "entity2", ...],
    "intent": "find_relationship|explain_connection|compare|causal|structural",
    "max_hops": 1|2|3
}}"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            extraction = json.loads(response.choices[0].message.content)

            # Update state
            state['query_entities'] = extraction.get('entities', [])
            state['query_intent'] = extraction.get('intent', 'find_relationship')
            state['max_hops'] = extraction.get('max_hops', 2)  # Default: 2-hop reasoning

            # Track cost
            tokens_used = response.usage.total_tokens
            state['total_cost'] = (tokens_used / 1000) * 0.02

            logger.info(
                "Entities extracted",
                entities=state['query_entities'],
                intent=state['query_intent'],
                max_hops=state['max_hops']
            )

            return state

        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            state['error_message'] = f"Entity extraction failed: {str(e)}"
            # Set defaults to continue pipeline
            state['query_entities'] = []
            state['query_intent'] = 'find_relationship'
            state['max_hops'] = 2
            return state

    async def _match_nodes(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 2: Match extracted entities to nodes in the knowledge graph.

        HOW NODE MATCHING WORKS:
        ------------------------
        The query mentions "climate change" but the graph might have:
        - Node: "Climate Change"
        - Node: "Global Warming" (synonym)
        - Node: "Environmental Impact" (related concept)

        We use fuzzy matching + LLM to find the best corresponding nodes:
        1. Search graph for nodes containing query entities (case-insensitive)
        2. Use LLM to disambiguate (e.g., "bank" → financial vs river bank)
        3. Return top matching nodes for each entity

        WHY NOT EXACT MATCH?
        --------------------
        Entity extraction might produce "AI" but graph has "Artificial Intelligence"
        Or query says "Einstein" but graph has "Albert Einstein"

        COST: Graph query is cheap (<1ms), LLM disambiguation adds ~$0.001
        """
        if not state['query_entities']:
            state['matched_nodes'] = []
            return state

        try:
            matched_nodes = []

            # For each entity, find matching nodes in graph
            for entity in state['query_entities']:
                # Query Neo4j for nodes matching this entity
                async with neo4j_service.driver.session() as session:
                    result = await session.run(
                        """
                        MATCH (e:Entity)
                        WHERE e.document_id = $doc_id
                        AND toLower(e.name) CONTAINS toLower($entity)
                        RETURN e.name as name, e.type as type
                        LIMIT 5
                        """,
                        doc_id=state['document_id'],
                        entity=entity
                    )

                    # Collect matching nodes
                    candidates = []
                    async for record in result:
                        candidates.append({
                            'name': record['name'],
                            'type': record['type'],
                            'query_entity': entity
                        })

                    if candidates:
                        # Use LLM to pick the best match (handles synonyms/disambiguation)
                        if len(candidates) > 1:
                            best_match = await self._disambiguate_nodes(
                                entity,
                                candidates,
                                state['user_query']
                            )
                            matched_nodes.append(best_match)
                        else:
                            matched_nodes.append(candidates[0])
                    else:
                        # No match found - log it
                        logger.warning("No graph node found for entity", entity=entity)

            state['matched_nodes'] = matched_nodes

            logger.info(
                "Nodes matched",
                query_entities=len(state['query_entities']),
                matched_nodes=len(matched_nodes)
            )

            return state

        except Exception as e:
            logger.error("Node matching failed", error=str(e))
            state['error_message'] = f"Node matching failed: {str(e)}"
            state['matched_nodes'] = []
            return state

    async def _disambiguate_nodes(
        self,
        entity: str,
        candidates: List[Dict],
        query: str
    ) -> Dict:
        """
        Use LLM to pick the best matching node when multiple candidates exist.

        Example:
        Entity: "bank"
        Candidates: ["River Bank", "Financial Bank", "Data Bank"]
        Query: "How do interest rates affect banks?"
        Result: "Financial Bank" (most relevant to context)
        """
        try:
            candidates_text = "\n".join([
                f"- {c['name']} (type: {c['type']})"
                for c in candidates
            ])

            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a disambiguation expert. Pick the most relevant node based on query context."
                    },
                    {
                        "role": "user",
                        "content": f"""Query: "{query}"
Entity to match: "{entity}"

Candidate nodes:
{candidates_text}

Which candidate best matches "{entity}" in the context of the query?
Respond with JSON: {{"best_match": "exact name from candidates"}}"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)
            best_name = result.get('best_match', candidates[0]['name'])

            # Find and return the matching candidate
            for c in candidates:
                if c['name'] == best_name:
                    return c

            return candidates[0]  # Fallback

        except Exception as e:
            logger.error("Disambiguation failed, using first candidate", error=str(e))
            return candidates[0]

    async def _discover_paths(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 3: Traverse the knowledge graph to discover relationship paths.

        GRAPH TRAVERSAL EXPLAINED:
        --------------------------
        Given nodes A and B, find paths connecting them:

        1-hop: A → B (direct relationship)
        Example: (Einstein)-[:DEVELOPED]->(Relativity)

        2-hop: A → X → B (one intermediate node)
        Example: (Einstein)-[:BORN_IN]->(Germany)-[:LOCATED_IN]->(Europe)

        3-hop: A → X → Y → B (two intermediate nodes)
        Example: (Einstein)-[:WORKED_AT]->(University)-[:LOCATED_IN]->(City)-[:HAS]->(Museum)

        CYPHER PATTERN MATCHING:
        ------------------------
        MATCH path = (a:Entity)-[r*1..3]-(b:Entity)

        This finds variable-length paths:
        - [r*1..3]: 1 to 3 relationships (hops)
        - (a)-[r]-(b): Undirected (finds both A→B and B→A)
        - RETURN relationships(path): Get all edges in the path

        WHY LIMIT HOPS?
        ---------------
        - 1-2 hops: Usually the most relevant, direct connections
        - 3+ hops: Combinatorial explosion (too many paths), often spurious
        - Graph can have millions of paths - we need focused results

        COST: Neo4j traversal is fast (ms), but scales with graph size
        """
        if not state['matched_nodes']:
            state['graph_paths'] = []
            state['confidence'] = 0.0
            return state

        try:
            # Build Cypher query to find paths between matched nodes
            # If we have multiple entities, find paths connecting them
            # If we have one entity, find its neighborhood

            if len(state['matched_nodes']) >= 2:
                # Multi-entity: Find paths connecting them
                paths = await self._find_connecting_paths(
                    state['document_id'],
                    state['matched_nodes'],
                    state['max_hops']
                )
            else:
                # Single entity: Find its neighborhood (what it connects to)
                paths = await self._find_entity_neighborhood(
                    state['document_id'],
                    state['matched_nodes'][0],
                    state['max_hops']
                )

            state['graph_paths'] = paths

            # Calculate confidence based on path relevance
            if paths:
                # More paths found = higher confidence (up to a point)
                # Fewer hops = higher quality
                avg_hops = sum(p.get('hops', 1) for p in paths) / len(paths)
                path_score = min(len(paths) / 5.0, 1.0)  # Normalize to 0-1
                hop_penalty = 1.0 / avg_hops  # Shorter paths are better
                state['confidence'] = min(path_score * hop_penalty, 1.0)
            else:
                state['confidence'] = 0.0

            logger.info(
                "Paths discovered",
                paths_found=len(paths),
                confidence=round(state['confidence'], 3)
            )

            return state

        except Exception as e:
            logger.error("Path discovery failed", error=str(e))
            state['error_message'] = f"Path discovery failed: {str(e)}"
            state['graph_paths'] = []
            state['confidence'] = 0.0
            return state

    async def _find_connecting_paths(
        self,
        document_id: int,
        nodes: List[Dict],
        max_hops: int
    ) -> List[Dict]:
        """Find paths connecting multiple entities"""
        async with neo4j_service.driver.session() as session:
            # Take first two matched nodes (can extend to handle more)
            node1 = nodes[0]['name']
            node2 = nodes[1]['name'] if len(nodes) > 1 else nodes[0]['name']

            result = await session.run(
                f"""
                MATCH path = (a:Entity)-[r*1..{max_hops}]-(b:Entity)
                WHERE a.document_id = $doc_id
                AND b.document_id = $doc_id
                AND a.name = $node1
                AND b.name = $node2
                RETURN [n in nodes(path) | n.name] as node_names,
                       [rel in relationships(path) | type(rel)] as rel_types,
                       length(path) as hops
                LIMIT 10
                """,
                doc_id=document_id,
                node1=node1,
                node2=node2
            )

            paths = []
            async for record in result:
                paths.append({
                    'nodes': record['node_names'],
                    'relationships': record['rel_types'],
                    'hops': record['hops']
                })

            return paths

    async def _find_entity_neighborhood(
        self,
        document_id: int,
        node: Dict,
        max_hops: int
    ) -> List[Dict]:
        """Find what an entity is connected to (its neighborhood)"""
        async with neo4j_service.driver.session() as session:
            result = await session.run(
                f"""
                MATCH path = (a:Entity)-[r*1..{max_hops}]-(b:Entity)
                WHERE a.document_id = $doc_id
                AND a.name = $node_name
                RETURN [n in nodes(path) | n.name] as node_names,
                       [rel in relationships(path) | type(rel)] as rel_types,
                       length(path) as hops
                LIMIT 15
                """,
                doc_id=document_id,
                node_name=node['name']
            )

            paths = []
            async for record in result:
                paths.append({
                    'nodes': record['node_names'],
                    'relationships': record['rel_types'],
                    'hops': record['hops']
                })

            return paths

    async def _generate_reasoning(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 4: Generate answer by reasoning over discovered paths.

        GRAPH-BASED REASONING:
        ----------------------
        Unlike vector RAG (which retrieves chunks), graph RAG retrieves RELATIONSHIPS.

        Example paths:
        1. (Einstein)-[:DEVELOPED]->(Relativity)
        2. (Relativity)-[:EXPLAINS]->(Gravity)
        3. (Gravity)-[:AFFECTS]->(Light)

        Answer to "How did Einstein explain light bending?":
        "Einstein developed Relativity, which explains Gravity. Gravity affects Light,
        causing it to bend. This forms a causal chain: Einstein → Relativity → Gravity → Light."

        STEP-BY-STEP REASONING:
        -----------------------
        The LLM doesn't just generate an answer - it explains the reasoning chain:
        1. Start node: Einstein
        2. Relationship: DEVELOPED
        3. Intermediate node: Relativity
        4. Relationship: EXPLAINS
        5. End node: Gravity

        This makes answers explainable and verifiable.

        COST: Most expensive step (~$0.01-0.03 depending on path complexity)
        """
        if not state['graph_paths']:
            state['final_answer'] = "I cannot answer this question as no relevant relationships were found in the knowledge graph."
            state['reasoning_chain'] = []
            return state

        try:
            # Format paths into readable text
            paths_text = self._format_paths_for_llm(state['graph_paths'])

            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a reasoning expert that explains how entities are connected in a knowledge graph.

Your task:
1. Analyze the relationship paths provided
2. Construct a logical reasoning chain
3. Generate a clear answer explaining HOW entities are connected
4. Show your reasoning step-by-step

Format:
- First, explain the reasoning chain
- Then, provide a direct answer
- Be concise but complete
- Use relationship names to explain connections"""
                    },
                    {
                        "role": "user",
                        "content": f"""Query: "{state['user_query']}"

Knowledge Graph Paths:
{paths_text}

Explain how these paths answer the query. Show the reasoning chain."""
                    }
                ],
                temperature=0.4,  # Slightly higher for natural reasoning
                max_tokens=600
            )

            full_response = response.choices[0].message.content

            # Parse reasoning chain and answer
            # (Simple split - could be more sophisticated)
            if "Answer:" in full_response:
                parts = full_response.split("Answer:")
                reasoning = parts[0].strip()
                answer = parts[1].strip()
            else:
                reasoning = ""
                answer = full_response

            state['final_answer'] = answer
            state['reasoning_chain'] = [reasoning] if reasoning else []

            # Track cost
            tokens_used = response.usage.total_tokens
            state['total_cost'] += (tokens_used / 1000) * 0.03

            logger.info(
                "Reasoning generated",
                answer_length=len(state['final_answer']),
                total_cost_usd=round(state['total_cost'], 4)
            )

            return state

        except Exception as e:
            logger.error("Reasoning generation failed", error=str(e))
            state['error_message'] = f"Reasoning failed: {str(e)}"
            state['final_answer'] = f"Error generating reasoning: {str(e)}"
            state['reasoning_chain'] = []
            return state

    def _format_paths_for_llm(self, paths: List[Dict]) -> str:
        """Format graph paths into readable text for the LLM"""
        formatted = []
        for i, path in enumerate(paths, 1):
            nodes = path['nodes']
            rels = path['relationships']

            # Build path string: A -[REL]-> B -[REL]-> C
            path_str = nodes[0]
            for j, rel in enumerate(rels):
                if j + 1 < len(nodes):
                    path_str += f" -[{rel}]-> {nodes[j+1]}"

            formatted.append(f"Path {i} ({path['hops']} hops): {path_str}")

        return "\n".join(formatted)

    async def query(
        self,
        document_id: int,
        user_query: str
    ) -> Dict:
        """
        Execute the full Graph RAG pipeline.

        Args:
            document_id: ID of the document to query
            user_query: User's natural language question

        Returns:
            Dict containing:
            - answer: Generated response with reasoning
            - reasoning_chain: Step-by-step explanation
            - graph_paths: Actual paths found in graph
            - confidence: 0.0-1.0 quality score
            - metadata: Cost, entities, processing steps

        Example:
            result = await agent.query(
                document_id=123,
                user_query="How does climate change affect polar bears?"
            )
            print(result['answer'])
            print("Reasoning:", result['reasoning_chain'])
        """
        # Initialize state
        initial_state = GraphRAGState(
            document_id=document_id,
            user_query=user_query,
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

        # Run through the state machine
        final_state = await self.workflow.ainvoke(initial_state)

        # Format response
        return {
            'answer': final_state['final_answer'],
            'reasoning_chain': final_state['reasoning_chain'],
            'confidence': round(final_state['confidence'], 3),
            'metadata': {
                'intent': final_state['query_intent'],
                'entities_extracted': final_state['query_entities'],
                'nodes_matched': len(final_state['matched_nodes']),
                'paths_found': len(final_state['graph_paths']),
                'max_hops': final_state['max_hops'],
                'total_cost_usd': round(final_state['total_cost'], 4),
                'error': final_state.get('error_message', '')
            },
            # Include actual paths for verification/debugging
            'graph_paths': [
                {
                    'nodes': path['nodes'],
                    'relationships': path['relationships'],
                    'hops': path['hops']
                }
                for path in final_state['graph_paths']
            ]
        }


# Global instance for easy import
graph_rag_agent = GraphRAGAgent()
