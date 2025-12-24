# Testing Guide - Phases 1 & 2

## Prerequisites

Ensure your environment is running:
```bash
# Start all services
cd backend
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected services:
- ✅ FastAPI backend (port 8000)
- ✅ Next.js frontend (port 3000)
- ✅ PostgreSQL (port 5432)
- ✅ Redis (port 6379)
- ✅ ChromaDB (port 4000)
- ✅ Neo4j (ports 7474, 7687)

## Step 1: Database Migration

Run the SQL migration to add RAG type fields:

```bash
# Connect to PostgreSQL
docker exec -it <postgres_container_name> psql -U <username> -d <database_name>

# Or if using local PostgreSQL
psql -U <username> -d <database_name>

# Run the migration
\i /path/to/backend/migrations/001_add_rag_type.sql

# Verify columns added
\d documents
```

Expected output should show:
- `rag_type` column (ragtype enum)
- `processing_metadata` column (jsonb)
- Index: `ix_documents_rag_type`

## Step 2: Backend Tests

```bash
cd backend

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio httpx

# Run WebSocket authentication tests
pytest tests/test_websocket_auth.py -v

# Run all tests
pytest tests/ -v
```

Expected results:
- ✅ All WebSocket auth tests pass
- ✅ Document upload tests pass
- ✅ Auth tests pass

## Step 3: Manual API Testing

### Test 1: User Registration & Login

```bash
# Register a new user
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123",
    "full_name": "Test User"
  }'

# Login to get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123"
```

Save the `access_token` from the response.

### Test 2: Document Upload with RAG Type Selection

```bash
# Set your token
TOKEN="<your_access_token_here>"

# Upload with Vector RAG (default)
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test.pdf" \
  -F "document_type=pdf" \
  -F "rag_type=vector"

# Upload with Graph RAG
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test.pdf" \
  -F "document_type=pdf" \
  -F "rag_type=graph"

# Upload with Hybrid RAG
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test.pdf" \
  -F "document_type=pdf" \
  -F "rag_type=hybrid"
```

Expected response should include:
```json
{
  "id": 1,
  "title": "test.pdf",
  "rag_type": "vector",  // or "graph" or "hybrid"
  "status": "processing",
  "processing_metadata": null  // Will be filled after processing
}
```

### Test 3: WebSocket Connection with JWT

```bash
# Using wscat (install: npm install -g wscat)
wscat -c "ws://localhost:8000/ws/connect?token=$TOKEN"

# Once connected, send a ping
> {"type": "ping"}

# Should receive
< {"type": "pong", "timestamp": 1234567890.123}
```

## Step 4: Frontend Testing

### Start Frontend Development Server

```bash
cd frontend
npm install  # if not already installed
npm run dev
```

Visit: http://localhost:3000

### Manual UI Tests

1. **Login/Signup**
   - Navigate to http://localhost:3000/login
   - Create account or login
   - Should redirect to dashboard

2. **RAG Type Selection**
   - Go to dashboard
   - Find document upload section
   - ✅ Verify 3 radio buttons: Vector, Graph, Hybrid
   - ✅ Each option shows description
   - ✅ Default selection is "Vector RAG"

3. **Document Upload**
   - Select "Graph RAG"
   - Upload a PDF file
   - ✅ Should show "Uploading with graph RAG..."
   - ✅ Document appears in list with 🕸️ badge
   - ✅ Check browser console - no errors

4. **WebSocket Connection**
   - Open browser DevTools → Console
   - Should see: "WebSocket connected successfully with JWT authentication"
   - Should see: "WebSocket message received: pong"
   - ✅ No authentication errors

## Step 5: Database Verification

```sql
-- Connect to database
-- Verify documents have RAG types

SELECT
    id,
    title,
    rag_type,
    status,
    processing_metadata->>'vector' as vector_meta,
    processing_metadata->>'graph' as graph_meta
FROM documents
ORDER BY created_at DESC
LIMIT 5;
```

Expected results:
- Vector RAG docs: `rag_type = 'vector'`, has `vector_meta`, no `graph_meta`
- Graph RAG docs: `rag_type = 'graph'`, has `graph_meta`, no `vector_meta`
- Hybrid RAG docs: `rag_type = 'hybrid'`, has both metas

## Step 6: ChromaDB Verification

```bash
# Check ChromaDB collections
curl http://localhost:4000/api/v1/collections

# Should see collections named: doc_1, doc_2, etc.
# Only for documents with rag_type='vector' or 'hybrid'
```

## Step 7: Neo4j Verification

Visit http://localhost:7474 (Neo4j Browser)

```cypher
// View all document nodes
MATCH (d:Document)
RETURN d

// View entities for a specific document
MATCH (d:Document {id: 1})-[:CONTAINS]->(e:Entity)
RETURN e

// Should only see data for rag_type='graph' or 'hybrid' documents
```

## Common Issues & Solutions

### Issue: Migration fails
**Solution**: Check if columns already exist. If so, skip migration or use ALTER IF NOT EXISTS.

### Issue: WebSocket auth fails
**Solution**:
- Verify token is valid (not expired)
- Check token is passed in URL: `?token=<JWT>`
- Check backend logs for auth errors

### Issue: Document upload stuck in "processing"
**Solution**:
- Check backend logs: `docker-compose logs backend`
- Verify ChromaDB is running: `curl http://localhost:4000/api/v1/heartbeat`
- Verify Neo4j is running: `curl http://localhost:7474`

### Issue: Frontend shows wrong RAG type
**Solution**:
- Clear browser cache
- Check API response includes `rag_type` field
- Verify DocumentResponse model includes `rag_type`

## Success Criteria

✅ **Phase 1 (WebSocket Security)**:
- WebSocket requires JWT token
- Invalid tokens are rejected
- Valid tokens connect successfully
- Auto-reconnect works

✅ **Phase 2 (RAG Selection)**:
- Database has `rag_type` column
- Users can select Vector/Graph/Hybrid
- Backend processes only selected type
- Processing metadata is stored correctly

## Next Steps

Once all tests pass:
1. Proceed to Phase 3: RAG Agents
2. Implement Vector RAG Agent (LangGraph)
3. Implement Graph RAG Agent (LangGraph)
4. Update AI endpoint routing
5. Create comprehensive test suite
6. Write educational documentation

## Monitoring

Keep these logs open during testing:

```bash
# Terminal 1: Backend logs
docker-compose logs -f backend

# Terminal 2: Frontend logs
cd frontend && npm run dev

# Terminal 3: PostgreSQL logs
docker-compose logs -f postgres

# Terminal 4: Run tests
pytest tests/ -v --log-cli-level=INFO
```
