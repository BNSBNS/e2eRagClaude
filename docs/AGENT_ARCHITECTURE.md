# Agent Architecture Guide

## Table of Contents
1. [What are Autonomous Agents?](#what-are-autonomous-agents)
2. [Why LangGraph?](#why-langgraph)
3. [Vector RAG Agent Architecture](#vector-rag-agent-architecture)
4. [Graph RAG Agent Architecture](#graph-rag-agent-architecture)
5. [Extending Agents](#extending-agents)
6. [Debugging & Monitoring](#debugging--monitoring)

---

## What are Autonomous Agents?

An **autonomous agent** is a system that can perform multi-step tasks with minimal human intervention.

### Traditional vs Agent-Based Approach

**Traditional RAG** (single-step):
```python
def query(question):
    chunks = vector_search(question)
    answer = llm(question, chunks)
    return answer
```

**Agent-Based RAG** (multi-step):
```python
def query(question):
    # Step 1: Understand query intent
    analysis = analyze_query(question)

    # Step 2: Adaptive retrieval based on complexity
    n_chunks = determine_chunk_count(analysis)
    chunks = vector_search(question, n_results=n_chunks)

    # Step 3: Filter irrelevant results
    relevant_chunks = rerank(chunks, question)

    # Step 4: Generate answer
    answer = generate_with_citations(question, relevant_chunks)

    return answer
```

### Why Use Agents?

| Aspect | Traditional | Agent-Based |
|--------|-------------|-------------|
| **Adaptability** | Fixed behavior | Adapts to query complexity |
| **Quality** | One-size-fits-all | Optimized per query |
| **Explainability** | Black box | Clear step-by-step process |
| **Debuggability** | Hard to diagnose | Inspect each step |
| **Cost** | Same for all queries | Optimized (simple queries cheaper) |

### Agent Components

1. **State**: Shared data structure that flows through steps
2. **Nodes**: Individual processing functions
3. **Edges**: Transitions between nodes
4. **Workflow**: The graph of nodes and edges

---

## Why LangGraph?

**LangGraph** is a framework for building stateful, multi-step agent workflows.

### LangGraph vs Alternatives

| Framework | Pros | Cons | Best For |
|-----------|------|------|----------|
| **LangGraph** | - Explicit state machines<br>- Easy testing<br>- TypedDict state | - Learning curve | Complex multi-step workflows |
| **LangChain Agents** | - Simple API<br>- Many pre-built | - Less control<br>- Hard to debug | Quick prototypes |
| **CrewAI** | - Multi-agent collaboration | - Heavyweight<br>- Opinionated | Team of agents |
| **Custom** | - Full control | - Reinvent the wheel | Very specific needs |

**We chose LangGraph** because:
1. **Testability**: Each node is a function we can test independently
2. **Visibility**: State machine makes flow explicit
3. **Debugging**: Can inspect state between steps
4. **Flexibility**: Can add conditional edges, loops, etc.

### Core Concepts

**State**:
```python
class VectorRAGState(TypedDict):
    user_query: str
    query_complexity: str  # simple/moderate/complex
    retrieved_chunks: List[Dict]
    final_answer: str
    # ... more fields
```

State flows through the graph:
```
Initial State → Node 1 → Updated State → Node 2 → Final State
```

**Nodes** (processing functions):
```python
async def analyze_query(state: VectorRAGState) -> VectorRAGState:
    # Read from state
    query = state['user_query']

    # Do processing
    complexity = classify_complexity(query)

    # Update state
    state['query_complexity'] = complexity

    return state
```

**Edges** (transitions):
```python
graph.add_edge("analyze_query", "retrieve_chunks")  # Always go to next node
graph.add_conditional_edges(                       # Conditional branching
    "check_results",
    lambda state: "retry" if len(state['chunks']) == 0 else "continue"
)
```

---

## Vector RAG Agent Architecture

**File**: `backend/app/services/agents/vector_rag_agent.py`

### State Machine Diagram

```
┌──────────────┐
│ User Query   │
└──────┬───────┘
       ↓
┌──────────────────────┐
│  Analyze Query       │  → Classify complexity, extract concepts
│  (LLM)               │  → Set n_results (3/5/8)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Retrieve Chunks     │  → Vector similarity search
│  (ChromaDB + OpenAI) │  → Get top N chunks
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Rerank Chunks       │  → LLM judges relevance
│  (LLM)               │  → Filter irrelevant
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Generate Answer     │  → LLM with context
│  (LLM)               │  → Extract citations
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Final Answer        │
│  + Confidence Score  │
│  + Sources          │
└──────────────────────┘
```

### Node Details

#### 1. Analyze Query

**Purpose**: Understand what the user is asking and how complex it is.

**Input**:
- `user_query`: "Compare supervised and unsupervised learning"

**Processing**:
```python
# LLM classifies query
{
    "intent": "comparison",
    "complexity": "moderate",  # → Will retrieve 5 chunks
    "key_concepts": ["supervised learning", "unsupervised learning"]
}
```

**Output**: Updated state with `query_complexity = "moderate"`, `n_results = 5`

**Why this step?**:
- Simple "What is X?" queries don't need 8 chunks (waste of money/time)
- Complex multi-concept queries need more context

#### 2. Retrieve Chunks

**Purpose**: Find semantically similar text chunks.

**Input**:
- `user_query`: The question
- `n_results`: How many chunks to retrieve (from step 1)

**Processing**:
```python
# Convert query to embedding
query_vector = openai.embed("Compare supervised and unsupervised learning")

# ChromaDB similarity search
results = chroma_db.query(query_embedding=query_vector, n_results=5)

# Calculate confidence from similarity scores
avg_similarity = mean([1 - distance for distance in results['distances']])
```

**Output**: `retrieved_chunks` with similarity scores, `confidence` score

**Why this step?**:
- Core retrieval mechanism
- Similarity scores help judge result quality

#### 3. Rerank Chunks

**Purpose**: Filter out chunks that mention keywords but don't actually answer the question.

**Input**:
- `retrieved_chunks`: Top 5 from vector search
- `user_query`: For relevance judging

**Processing**:
```python
# LLM evaluates each chunk
prompt = f"""
Query: {query}
Chunks: {chunks}

Which chunks ACTUALLY help answer this question?
Return indices: [0, 2, 4]
"""

# Keep only relevant indices
kept_chunks = [chunks[i] for i in relevant_indices]
```

**Output**: `reranked_chunks` (subset of retrieved_chunks)

**Why this step?**:
- Vector similarity ≠ semantic relevance
- Example: "bank" (financial) vs "bank" (river) both have high similarity

**Can skip**: For simple queries to save cost (not implemented yet)

#### 4. Generate Answer

**Purpose**: Create final answer with citations.

**Input**:
- `reranked_chunks`: Most relevant context
- `user_query`: The question

**Processing**:
```python
context = "\n".join([f"[Source {i+1}]: {chunk}" for i, chunk in enumerate(chunks)])

prompt = f"""
Context: {context}
Question: {query}

Answer using ONLY the context above. Cite sources as [Source N].
"""

answer = llm(prompt)
```

**Output**: `final_answer` with citations, `sources` list

**Why this step?**:
- Generates the actual answer
- Citations allow verification

### State Flow Example

**Query**: "What is machine learning?"

**State Evolution**:
```python
# Initial
{
    'user_query': 'What is machine learning?',
    'query_complexity': '',
    'n_results': 0,
    'retrieved_chunks': [],
    'reranked_chunks': [],
    'final_answer': '',
    'confidence': 0.0
}

# After analyze_query
{
    'query_complexity': 'simple',
    'n_results': 3,  # Simple = 3 chunks
    # ... rest unchanged
}

# After retrieve_chunks
{
    'retrieved_chunks': [
        {'text': 'ML is a subset of AI...', 'similarity': 0.92},
        {'text': 'Neural networks...', 'similarity': 0.81},
        {'text': 'Deep learning...', 'similarity': 0.79}
    ],
    'confidence': 0.84,  # Avg similarity
    # ... rest unchanged
}

# After rerank_chunks
{
    'reranked_chunks': [  # Kept all 3 (all relevant)
        {'text': 'ML is a subset of AI...', 'similarity': 0.92},
        {'text': 'Neural networks...', 'similarity': 0.81},
        {'text': 'Deep learning...', 'similarity': 0.79}
    ],
    # ... rest unchanged
}

# After generate_answer
{
    'final_answer': 'Machine learning is a subset of AI that focuses on learning from data [Source 1]...',
    'sources': [0],  # Used chunk 0
    # ... rest unchanged
}
```

### Code Structure

```python
class VectorRAGAgent:
    def __init__(self):
        self.workflow = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(VectorRAGState)
        graph.add_node("analyze_query", self._analyze_query)
        graph.add_node("retrieve_chunks", self._retrieve_chunks)
        # ... more nodes
        graph.add_edge("analyze_query", "retrieve_chunks")
        # ... more edges
        return graph.compile()

    async def _analyze_query(self, state):
        # Implementation
        return updated_state

    async def query(self, document_id, user_query):
        initial_state = {...}
        final_state = await self.workflow.ainvoke(initial_state)
        return format_response(final_state)
```

---

## Graph RAG Agent Architecture

**File**: `backend/app/services/agents/graph_rag_agent.py`

### State Machine Diagram

```
┌──────────────┐
│ User Query   │
└──────┬───────┘
       ↓
┌──────────────────────┐
│  Extract Entities    │  → Find entities in query
│  (LLM)               │  → Determine intent & hop depth
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Match Nodes         │  → Find entities in Neo4j
│  (Neo4j + LLM)       │  → Disambiguate if needed
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Discover Paths      │  → Cypher graph traversal
│  (Neo4j)             │  → Find relationships (1-3 hops)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Generate Reasoning  │  → Explain relationship chain
│  (LLM)               │  → Synthesize answer
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Final Answer        │
│  + Reasoning Chain   │
│  + Graph Paths       │
└──────────────────────┘
```

### Node Details

#### 1. Extract Entities

**Purpose**: Identify what the query is about.

**Input**:
- `user_query`: "How does climate change affect polar bears?"

**Processing**:
```python
# LLM extracts entities and determines intent
{
    "entities": ["climate change", "polar bears"],
    "intent": "causal",  # Asking about cause-effect
    "max_hops": 3  # Might need indirect connections
}
```

**Output**: `query_entities`, `query_intent`, `max_hops`

**Why this step?**:
- Graphs work with entities, not full questions
- Intent determines traversal strategy

#### 2. Match Nodes

**Purpose**: Map query entities to graph nodes.

**Input**:
- `query_entities`: ["climate change", "polar bears"]

**Processing**:
```python
# For each entity, search Neo4j
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower("climate change")
AND e.document_id = $doc_id
RETURN e

# Results:
# - "Climate Change" (exact match)
# - "Global Warming" (synonym)

# LLM disambiguates if multiple matches
best_match = llm_pick_most_relevant(candidates, query_context)
```

**Output**: `matched_nodes` (entities found in graph)

**Why this step?**:
- Query might say "Einstein" but graph has "Albert Einstein"
- Need fuzzy matching + disambiguation

#### 3. Discover Paths

**Purpose**: Find how entities are connected.

**Input**:
- `matched_nodes`: [Climate Change node, Polar Bears node]
- `max_hops`: 3

**Processing**:
```python
# Cypher query to find paths
MATCH path = (a:Entity)-[*1..3]-(b:Entity)
WHERE a.name = "Climate Change"
AND b.name = "Polar Bears"
RETURN path

# Might find:
# (Climate Change)-[CAUSES]->(Ice Melting)-[REDUCES]->(Habitat)-[NEEDED_BY]->(Polar Bears)
```

**Output**: `graph_paths` with nodes and relationships

**Why this step?**:
- This is the core graph reasoning
- Uncovers indirect relationships

#### 4. Generate Reasoning

**Purpose**: Explain the discovered connections.

**Input**:
- `graph_paths`: The relationship chains
- `user_query`: Original question

**Processing**:
```python
# Format paths for LLM
paths_text = """
Path 1: Climate Change -[CAUSES]-> Ice Melting -[REDUCES]-> Habitat -[NEEDED_BY]-> Polar Bears
"""

prompt = f"""
Query: {query}
Paths: {paths_text}

Explain the reasoning chain showing how these paths answer the query.
"""

# LLM constructs explanation
```

**Output**: `final_answer`, `reasoning_chain`

**Why this step?**:
- Raw paths aren't human-friendly
- Need natural language explanation

### Comparison with Vector Agent

| Aspect | Vector Agent | Graph Agent |
|--------|--------------|-------------|
| **Input Processing** | Query → Embedding | Query → Entities |
| **Retrieval** | Similarity search | Graph traversal |
| **Result Type** | Text chunks | Relationship paths |
| **Reasoning** | Implicit (in LLM) | Explicit (in graph) |
| **Strength** | Facts | Connections |

---

## Extending Agents

### Adding a New Node

**Example**: Add a "Fact Checking" node to Vector RAG Agent.

```python
# 1. Update state definition
class VectorRAGState(TypedDict):
    # ... existing fields
    fact_check_result: str  # NEW
    contradictions_found: List[str]  # NEW

# 2. Implement node function
async def _fact_check(self, state: VectorRAGState) -> VectorRAGState:
    """Verify facts in answer against source chunks"""
    answer = state['final_answer']
    chunks = state['reranked_chunks']

    # Check each claim in answer
    claims = extract_claims(answer)
    contradictions = []

    for claim in claims:
        if not verify_claim_in_chunks(claim, chunks):
            contradictions.append(claim)

    state['contradictions_found'] = contradictions
    state['fact_check_result'] = "PASS" if len(contradictions) == 0 else "FAIL"

    return state

# 3. Add to graph
def _build_graph(self):
    graph = StateGraph(VectorRAGState)
    # ... existing nodes
    graph.add_node("fact_check", self._fact_check)  # NEW

    # Insert into workflow
    graph.add_edge("generate_answer", "fact_check")  # NEW
    graph.add_edge("fact_check", END)

    return graph.compile()
```

### Adding Conditional Logic

**Example**: Retry retrieval if confidence is too low.

```python
def _build_graph(self):
    graph = StateGraph(VectorRAGState)

    # Add all nodes
    graph.add_node("retrieve", self._retrieve)
    graph.add_node("check_confidence", self._check_confidence)
    graph.add_node("expand_search", self._expand_search)
    graph.add_node("generate", self._generate)

    # Conditional edge
    graph.add_conditional_edges(
        "check_confidence",
        lambda state: "retry" if state['confidence'] < 0.5 else "continue",
        {
            "retry": "expand_search",  # Low confidence → expand search
            "continue": "generate"      # Good confidence → proceed
        }
    )

    graph.add_edge("expand_search", "retrieve")  # Loop back

    return graph.compile()
```

### Adding a New Agent

**Example**: Summarization Agent.

```python
# 1. Create new file: backend/app/services/agents/summarization_agent.py

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SummaryState(TypedDict):
    document_text: str
    summary_length: str  # "short", "medium", "long"
    key_points: List[str]
    summary: str

class SummarizationAgent:
    def __init__(self):
        self.workflow = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(SummaryState)

        graph.add_node("extract_key_points", self._extract_key_points)
        graph.add_node("generate_summary", self._generate_summary)

        graph.add_edge("extract_key_points", "generate_summary")
        graph.add_edge("generate_summary", END)

        graph.set_entry_point("extract_key_points")

        return graph.compile()

    async def _extract_key_points(self, state):
        # LLM extracts main ideas
        ...

    async def _generate_summary(self, state):
        # LLM creates summary from key points
        ...

    async def summarize(self, document_text, length="medium"):
        initial_state = {
            'document_text': document_text,
            'summary_length': length,
            'key_points': [],
            'summary': ''
        }
        final_state = await self.workflow.ainvoke(initial_state)
        return final_state['summary']

# 2. Add to routing logic in api/ai.py
from services.agents.summarization_agent import summarization_agent

@router.post("/summarize/{document_id}")
async def summarize_document(document_id: int, length: str = "medium"):
    document = await DocumentService.get_document_by_id(...)
    summary = await summarization_agent.summarize(document.extracted_text, length)
    return {"summary": summary}
```

---

## Debugging & Monitoring

### Inspecting State Between Steps

**During Development**:
```python
async def _analyze_query(self, state):
    # ... processing

    # Add logging
    logger.info("Query analysis complete",
                complexity=state['query_complexity'],
                n_results=state['n_results'])

    # Can even print state for debugging
    print(json.dumps(state, indent=2))

    return state
```

**In Production**:
Use structured logging (already implemented with `structlog`).

### Testing Individual Nodes

```python
# tests/test_vector_agent.py

async def test_analyze_query_classifies_simple_queries():
    agent = VectorRAGAgent()

    state = VectorRAGState(
        user_query="What is X?",
        # ... initialize all fields
    )

    result = await agent._analyze_query(state)

    assert result['query_complexity'] == 'simple'
    assert result['n_results'] == 3
```

This is why LangGraph is powerful: Each node is just a function you can test!

### Monitoring in Production

**Add metrics collection**:
```python
async def _retrieve_chunks(self, state):
    start_time = time.time()

    # ... retrieval logic

    duration = time.time() - start_time

    metrics.record({
        'operation': 'vector_retrieve',
        'duration_ms': duration * 1000,
        'chunks_found': len(state['retrieved_chunks']),
        'confidence': state['confidence']
    })

    return state
```

**Track costs**:
Already implemented! Each node updates `state['total_cost']`.

```python
# Final state includes
{
    'metadata': {
        'total_cost_usd': 0.0234  # Sum of all LLM calls
    }
}
```

### Common Debugging Scenarios

**Problem**: Agent returns "Cannot answer"

**Debug**:
1. Check `retrieved_chunks` - Were any chunks found?
2. Check `confidence` score - Is similarity too low?
3. Check `reranked_chunks` - Did reranking filter everything out?
4. Check LLM logs - Is the generation prompt malformed?

**Problem**: Wrong answer

**Debug**:
1. Inspect `retrieved_chunks` - Are the RIGHT chunks being retrieved?
2. Check `sources` - Which chunks did the LLM use?
3. Verify chunks actually contain correct information
4. Test if retrieval or generation is the issue

---

## Best Practices

### 1. Keep Nodes Focused

❌ **Bad**:
```python
async def process_query(self, state):
    # Analyze query
    analysis = analyze(state['query'])

    # Retrieve chunks
    chunks = retrieve(state['query'])

    # Generate answer
    answer = generate(chunks)

    return state  # One mega-node
```

✅ **Good**:
```python
async def analyze_query(self, state):
    state['analysis'] = analyze(state['query'])
    return state

async def retrieve_chunks(self, state):
    state['chunks'] = retrieve(state['query'], state['analysis'])
    return state

async def generate_answer(self, state):
    state['answer'] = generate(state['chunks'])
    return state
```

**Why**: Focused nodes are easier to test, debug, and reuse.

### 2. Use TypedDict for State

✅ Always use `TypedDict` for type safety:
```python
class MyState(TypedDict):
    field1: str
    field2: int

# IDE autocomplete works!
# Type checker catches errors!
```

### 3. Handle Errors Gracefully

```python
async def _some_node(self, state):
    try:
        result = await risky_operation()
        state['result'] = result
    except Exception as e:
        logger.error("Node failed", error=str(e))
        state['error_message'] = str(e)
        # Set safe defaults so workflow can continue
        state['result'] = default_value

    return state
```

### 4. Log Generously

```python
logger.info("Node starting", node="analyze_query", query_length=len(state['user_query']))
# ... processing
logger.info("Node complete", node="analyze_query", complexity=state['complexity'])
```

---

## Conclusion

Autonomous agents with LangGraph provide:
- **Adaptability**: Different behavior per query
- **Explainability**: Clear step-by-step flow
- **Testability**: Each node is independently testable
- **Extensibility**: Easy to add new capabilities

The Vector and Graph RAG agents in this system demonstrate real-world agent patterns that can be adapted to many use cases beyond RAG.

**Next Steps**: Try extending the agents with your own nodes!
