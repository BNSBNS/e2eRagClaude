# RAG Explained: From Ground Up

## Table of Contents
1. [What is RAG?](#what-is-rag)
2. [Vector RAG Deep Dive](#vector-rag-deep-dive)
3. [Graph RAG Deep Dive](#graph-rag-deep-dive)
4. [Hybrid RAG](#hybrid-rag)
5. [When to Use Which?](#when-to-use-which)
6. [Implementation in This System](#implementation-in-this-system)

---

## What is RAG?

**RAG (Retrieval-Augmented Generation)** is a technique that enhances Large Language Models (LLMs) by providing them with relevant external information.

### The Core Problem RAG Solves

LLMs have two major limitations:
1. **Knowledge cutoff**: They only know information up to their training date
2. **No private data**: They can't access your specific documents/databases

### How RAG Works

```
User Question
    ↓
Retrieve relevant information from your data
    ↓
Combine question + retrieved context
    ↓
Send to LLM for answer generation
    ↓
Answer grounded in your data
```

### Why RAG Instead of Fine-Tuning?

| Approach | Pros | Cons |
|----------|------|------|
| **Fine-tuning** | - Deep knowledge integration | - Expensive ($1000s)<br>- Static (can't update)<br>- Slow (days/weeks) |
| **RAG** | - Cheap ($0.01 per query)<br>- Dynamic (update anytime)<br>- Fast (milliseconds) | - Relies on retrieval quality<br>- Context window limits |

**Verdict**: RAG is better for most use cases involving private/dynamic data.

---

## Vector RAG Deep Dive

Vector RAG uses **semantic similarity** to find relevant information.

### Step 1: Text → Embeddings

Embeddings convert text into numerical vectors that capture meaning:

```python
"machine learning" → [0.24, -0.87, 0.61, ..., 0.33]  # 1536 dimensions (OpenAI ada-002)
"AI algorithms"    → [0.22, -0.85, 0.59, ..., 0.31]  # Similar vector!
"banana recipe"    → [0.91, 0.14, -0.72, ..., -0.44] # Very different vector
```

**Key Insight**: Similar meanings → similar vectors.

**How embeddings work**:
- Trained on billions of text pairs
- Words used in similar contexts get similar vectors
- Captures synonyms, related concepts, even analogies

### Step 2: Store in Vector Database

Your document gets:
1. **Chunked**: Split into ~500-token pieces (for context window limits)
2. **Embedded**: Each chunk → vector
3. **Stored**: Vectors go into ChromaDB (or Pinecone, Weaviate, etc.)

```
Document: "Machine learning is a subset of AI..."
    ↓ Chunk
Chunk 1: "Machine learning is a subset of AI that..."  → Vector A
Chunk 2: "Neural networks are computational models..." → Vector B
Chunk 3: "Deep learning uses multiple layers..."       → Vector C
    ↓ Store
ChromaDB Collection
```

### Step 3: Similarity Search

When user asks: "What is machine learning?"

```python
1. Query → Embedding
   "What is machine learning?" → Query Vector Q

2. Compare to all stored vectors using Cosine Similarity
   Similarity(Q, Vector A) = 0.92  # Very similar!
   Similarity(Q, Vector B) = 0.75  # Somewhat related
   Similarity(Q, Vector C) = 0.81  # Related

3. Return top N most similar chunks
   Result: [Chunk 1, Chunk 3, Chunk 2]  # Ranked by similarity
```

**Cosine Similarity** measures angle between vectors:
- **1.0** = Identical direction (perfect semantic match)
- **0.0** = Perpendicular (unrelated concepts)
- **-1.0** = Opposite direction (contradictory, rare)

Formula: `cos(θ) = (A · B) / (||A|| ||B||)`

### Step 4: Generate Answer with Context

```python
Context = """
[Chunk 1]: Machine learning is a subset of AI that focuses on learning from data.
[Chunk 2]: Deep learning uses multiple layers to learn hierarchical representations.
"""

Prompt to LLM:
"Use ONLY this context to answer: What is machine learning?
Context: {Context}"

LLM Response:
"Machine learning is a subset of AI that focuses on learning from data [Chunk 1]."
```

### Technical Details

**Embedding Models**:
- OpenAI `text-embedding-ada-002`: 1536 dimensions, $0.0001/1K tokens
- OpenAI `text-embedding-3-small`: 1536 dims, better performance
- Open-source: `sentence-transformers` (free, run locally)

**Vector Databases**:
- **ChromaDB**: SQLite-based, great for prototypes
- **Pinecone**: Managed, scales to billions of vectors
- **Weaviate**: Open-source, GraphQL API

**Search Algorithms**:
- **Brute Force**: O(N) - Compare to every vector (slow for large N)
- **HNSW (Hierarchical Navigable Small World)**: O(log N) - Fast approximate search
  - Used by ChromaDB and most production systems
  - 99%+ accuracy, 100x faster than brute force

### Pros and Cons

✅ **Pros**:
- **Fast**: Millisecond search times
- **Scalable**: Handle millions of documents
- **Simple**: Straightforward to implement
- **General**: Works for any text data

❌ **Cons**:
- **No reasoning**: Can't answer "Why does X cause Y?"
- **Surface-level**: Finds mentions, not deep connections
- **Context limits**: Can only use top-K chunks (typically 3-5)
- **Embedding quality**: Depends on embedding model understanding nuance

---

## Graph RAG Deep Dive

Graph RAG uses **knowledge graphs** to capture relationships and enable reasoning.

### What is a Knowledge Graph?

A graph with:
- **Nodes**: Entities (people, concepts, things)
- **Edges**: Relationships between entities

```
(Einstein)-[:DEVELOPED]->(Relativity)
(Relativity)-[:EXPLAINS]->(Gravity)
(Gravity)-[:AFFECTS]->(Light)
```

Unlike vector databases (unstructured chunks), graphs capture **structure**.

### Step 1: Entity & Relationship Extraction

From text: "Einstein developed the theory of relativity, which explains how gravity affects light."

Extract:
```
Entities:
- Einstein (Person)
- Theory of Relativity (Concept)
- Gravity (Force)
- Light (Phenomenon)

Relationships:
- Einstein → DEVELOPED → Theory of Relativity
- Theory of Relativity → EXPLAINS → Gravity
- Gravity → AFFECTS → Light
```

**How extraction works**:
1. **Named Entity Recognition (NER)**: Identify entities
2. **Relationship Classification**: Determine how entities relate
3. **LLM-based** (this system): GPT-4 extracts structured data

```python
prompt = "Extract entities and relationships from: {text}"
response = llm(prompt)
# Returns: {"entities": [...], "relationships": [...]}
```

### Step 2: Store in Graph Database (Neo4j)

```cypher
// Create nodes
CREATE (e:Person {name: "Einstein"})
CREATE (r:Concept {name: "Relativity"})
CREATE (g:Force {name: "Gravity"})
CREATE (l:Phenomenon {name: "Light"})

// Create relationships
CREATE (e)-[:DEVELOPED]->(r)
CREATE (r)-[:EXPLAINS]->(g)
CREATE (g)-[:AFFECTS]->(l)
```

### Step 3: Graph Traversal & Pattern Matching

Query: "How did Einstein's work affect light?"

**Cypher Query** (Neo4j's query language):
```cypher
MATCH path = (einstein:Person {name: "Einstein"})-[*1..3]-(light:Phenomenon {name: "Light"})
RETURN path
```

This finds all paths between Einstein and Light with 1-3 hops (relationships).

**Result**:
```
Path 1: (Einstein)-[:DEVELOPED]->(Relativity)-[:EXPLAINS]->(Gravity)-[:AFFECTS]->(Light)
```

**Multi-hop reasoning**:
- **1-hop**: Direct connection (A → B)
- **2-hop**: One intermediate node (A → X → B)
- **3-hop**: Two intermediate nodes (A → X → Y → B)

Why limit hops? Combinatorial explosion:
- 1-hop: 10 paths
- 2-hop: 100 paths
- 3-hop: 1,000 paths
- 4-hop: 10,000 paths (mostly irrelevant)

### Step 4: Generate Answer with Graph Context

```python
Graph Paths:
Path 1: Einstein -[DEVELOPED]-> Relativity -[EXPLAINS]-> Gravity -[AFFECTS]-> Light

Prompt to LLM:
"Based on these relationship paths, explain how Einstein's work affected light.
Paths: {graph_paths}"

LLM Response:
"Einstein developed the theory of Relativity, which explains Gravity.
Gravity affects Light, causing it to bend near massive objects.
Therefore, Einstein's work provided the theoretical framework for understanding light bending."
```

**Key difference from Vector RAG**: The answer explains the **chain of reasoning**, not just facts.

### Graph Algorithms Used

**Shortest Path**:
```cypher
MATCH (a:Person {name: "Einstein"}), (b:Phenomenon {name: "Light"}),
      path = shortestPath((a)-[*]-(b))
RETURN path
```

**Community Detection**: Find clusters of related concepts

**Centrality**: Identify most important nodes
- PageRank: Which concepts are most referenced?
- Betweenness: Which concepts connect different areas?

### Pros and Cons

✅ **Pros**:
- **Reasoning**: Can answer "how" and "why" questions
- **Explainable**: Shows exact relationship chain
- **Multi-hop**: Discovers indirect connections
- **Structured**: Captures domain knowledge explicitly

❌ **Cons**:
- **Extraction quality**: Depends on entity/relationship extraction
- **Slower**: Graph traversal slower than vector lookup
- **Complexity**: Requires graph database setup
- **Sparse**: Only works if relationships exist in graph

---

## Hybrid RAG

Combines both approaches for maximum power.

### Why Hybrid?

Different queries need different retrieval:
- **"What is X?"** → Vector RAG (fact lookup)
- **"How does X affect Y?"** → Graph RAG (relationship reasoning)
- **"Explain X and its connections to Y and Z"** → Hybrid (both!)

### How It Works in This System

```
User uploads document with "Hybrid" selected
    ↓
BOTH processing pipelines run:
    ├─ Vector: Chunk → Embed → Store in ChromaDB
    └─ Graph: Extract entities → Store in Neo4j

User asks question
    ↓
BOTH agents run in parallel:
    ├─ Vector Agent: Retrieves relevant chunks
    └─ Graph Agent: Finds relationship paths

LLM synthesizes both perspectives
    ↓
Final answer with:
    - Factual content (from chunks)
    - Relationship reasoning (from graph)
```

### Example

**Question**: "How does climate change affect polar bears?"

**Vector RAG Answer**:
"Climate change is causing Arctic ice to melt. Polar bears depend on sea ice for hunting seals [Chunk 5]."

**Graph RAG Answer**:
"Climate Change -[CAUSES]-> Ice Melting -[REDUCES]-> Hunting Grounds -[NEEDED_BY]-> Polar Bears.
The relationship chain shows climate change indirectly affects polar bears through habitat destruction."

**Hybrid Synthesized Answer**:
"Climate change is causing Arctic ice to melt [Chunk 5], which reduces the hunting grounds that polar bears need for survival. The relationship chain (Climate Change → Ice Melting → Hunting Grounds → Polar Bears) shows how environmental changes cascade to impact wildlife populations."

### Trade-offs

| Aspect | Hybrid | Vector Only | Graph Only |
|--------|--------|-------------|------------|
| **Accuracy** | Highest | Good | Good |
| **Cost** | 2x | Baseline | Baseline |
| **Speed** | Slowest | Fastest | Medium |
| **Processing** | 2x time | Fast | Medium |

**Use hybrid when**: Maximum accuracy matters more than cost/speed.

---

## When to Use Which?

### Use Vector RAG When:
- ✓ Simple fact lookup ("What is X?", "When did Y happen?")
- ✓ Finding similar content ("Find documents like this")
- ✓ Q&A over large documents
- ✓ Speed is critical
- ✓ Cost optimization needed

**Example queries**:
- "What are the ingredients in this recipe?"
- "What did the CEO say about revenue?"
- "Summarize this research paper"

### Use Graph RAG When:
- ✓ Relationship questions ("How does X relate to Y?")
- ✓ Causal reasoning ("Why did X happen?")
- ✓ Multi-hop logic ("If A causes B, and B affects C, what about D?")
- ✓ Comparison ("What do X and Y have in common?")
- ✓ Explainability matters

**Example queries**:
- "How does inflation affect interest rates?"
- "What's the connection between these two proteins?"
- "Why did the stock price drop after the announcement?"

### Use Hybrid When:
- ✓ Complex analytical tasks
- ✓ Research/academic work
- ✓ Maximum accuracy needed
- ✓ Budget allows

**Example queries**:
- "Analyze the relationship between marketing spend and revenue, including specific examples"
- "Explain the causal chain from user behavior to business outcomes"

---

## Implementation in This System

### Architecture Overview

```
Frontend (Next.js)
    ↓
User selects RAG type at upload: Vector / Graph / Hybrid
    ↓
Backend (FastAPI)
    ↓
Conditional Processing:
    IF Vector or Hybrid:
        - Chunk document
        - Create embeddings (OpenAI ada-002)
        - Store in ChromaDB

    IF Graph or Hybrid:
        - Extract entities (GPT-4)
        - Extract relationships
        - Create graph in Neo4j
    ↓
Query Time:
    Document's rag_type determines which agent runs
    ↓
Vector Agent (LangGraph):
    1. Analyze query
    2. Adaptive retrieval (3-8 chunks based on complexity)
    3. Rerank with LLM
    4. Generate answer with citations

Graph Agent (LangGraph):
    1. Extract entities from query
    2. Match to graph nodes
    3. Discover paths (1-3 hops)
    4. Generate reasoning chain

Hybrid:
    - Run both agents in parallel
    - Synthesize with LLM
```

### Tech Stack

| Component | Technology | Why? |
|-----------|-----------|------|
| **Embeddings** | OpenAI ada-002 | Best quality/cost ratio |
| **Vector DB** | ChromaDB | Easy setup, HNSW index |
| **Graph DB** | Neo4j | Industry standard, Cypher |
| **LLM** | GPT-4 | Best reasoning for agents |
| **Agent Framework** | LangGraph | State machines for complex flows |
| **Backend** | FastAPI | Async, fast, Python |
| **Frontend** | Next.js | React, TypeScript, modern |

### Code References

- **Vector Agent**: `backend/app/services/agents/vector_rag_agent.py`
- **Graph Agent**: `backend/app/services/agents/graph_rag_agent.py`
- **AI Routing**: `backend/app/api/ai.py`
- **Document Processing**: `backend/app/services/document_service.py`

### Performance Characteristics

**Vector RAG**:
- Query latency: 200-500ms
- Cost per query: $0.01-0.03
- Scales to: Millions of documents

**Graph RAG**:
- Query latency: 500-1500ms
- Cost per query: $0.02-0.05
- Scales to: Thousands of documents (graph traversal limits)

**Hybrid**:
- Query latency: 1-2 seconds
- Cost per query: $0.03-0.08

### Optimizations Implemented

1. **Adaptive Retrieval**: Simple queries get 3 chunks, complex get 8 (saves cost)
2. **Reranking**: Filters irrelevant chunks before expensive LLM call
3. **Parallel Agents**: Hybrid mode runs both agents concurrently
4. **Caching**: (Not yet implemented - future enhancement)

---

## Further Learning

### Academic Papers

- **Vector RAG**: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al., 2020)
- **Graph RAG**: "From Local to Global: A Graph RAG Approach" (Microsoft Research, 2024)

### Resources

- **Vector Embeddings**: [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- **Neo4j Cypher**: [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- **LangGraph**: [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

### Experiment Yourself

Try different queries on the same document with Vector vs Graph:
1. Upload a document with "Hybrid" selected
2. Ask a factual question → Compare which agent performs better
3. Ask a relationship question → Compare again
4. Notice the differences in answer quality and reasoning depth

---

## Conclusion

**RAG** is not one technique - it's a family of approaches for grounding LLMs in external data.

- **Vector RAG**: Fast, scalable, good for facts
- **Graph RAG**: Reasoning, explainable, good for relationships
- **Hybrid**: Best of both, at 2x cost

The right choice depends on your use case. This system gives you control to choose per document, allowing experimentation to find what works best for your data.
