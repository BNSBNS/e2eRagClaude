#!/bin/bash
# Comprehensive test runner for all phases

echo "============================================"
echo "Running Complete Test Suite (Phases 1-4)"
echo "============================================"
echo ""

# Set PYTHONPATH to include app directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/app"

# Load test environment variables
if [ -f .env.test ]; then
    export $(cat .env.test | grep -v '^#' | xargs)
    echo "✓ Test environment loaded from .env.test"
else
    echo "⚠ Warning: .env.test not found, using system environment"
fi
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Phase 1: Security Tests
echo -e "${YELLOW}Phase 1: Security${NC}"
echo "Testing WebSocket Authentication..."
pytest tests/test_websocket_auth.py -v
WS_RESULT=$?

echo ""
echo "Testing User Authentication..."
pytest tests/test_auth.py -v
AUTH_RESULT=$?

# Phase 2: Document Processing Tests
echo ""
echo -e "${YELLOW}Phase 2: Document Processing${NC}"
echo "Testing Document Upload..."
pytest tests/test_documents.py -v
DOC_RESULT=$?

# Phase 3: RAG Agent Tests
echo ""
echo -e "${YELLOW}Phase 3: RAG Agents${NC}"
echo "Testing Vector RAG Agent..."
pytest tests/test_vector_rag_agent.py -v
VECTOR_AGENT_RESULT=$?

echo ""
echo "Testing Graph RAG Agent..."
pytest tests/test_graph_rag_agent.py -v
GRAPH_AGENT_RESULT=$?

echo ""
echo "Testing AI Endpoint Routing..."
pytest tests/test_ai_routing.py -v
ROUTING_RESULT=$?

# Summary
echo ""
echo "============================================"
echo "Test Summary"
echo "============================================"

# Phase 1
echo -e "${YELLOW}Phase 1: Security${NC}"
if [ $WS_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} WebSocket Auth Tests: PASSED"
else
    echo -e "${RED}✗${NC} WebSocket Auth Tests: FAILED"
fi

if [ $AUTH_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} User Auth Tests: PASSED"
else
    echo -e "${RED}✗${NC} User Auth Tests: FAILED"
fi

# Phase 2
echo ""
echo -e "${YELLOW}Phase 2: Document Processing${NC}"
if [ $DOC_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Document Tests: PASSED"
else
    echo -e "${RED}✗${NC} Document Tests: FAILED"
fi

# Phase 3
echo ""
echo -e "${YELLOW}Phase 3: RAG Agents${NC}"
if [ $VECTOR_AGENT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Vector RAG Agent Tests: PASSED"
else
    echo -e "${RED}✗${NC} Vector RAG Agent Tests: FAILED"
fi

if [ $GRAPH_AGENT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Graph RAG Agent Tests: PASSED"
else
    echo -e "${RED}✗${NC} Graph RAG Agent Tests: FAILED"
fi

if [ $ROUTING_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} AI Routing Tests: PASSED"
else
    echo -e "${RED}✗${NC} AI Routing Tests: FAILED"
fi

# Overall result
echo ""
echo "============================================"
if [ $WS_RESULT -eq 0 ] && [ $AUTH_RESULT -eq 0 ] && [ $DOC_RESULT -eq 0 ] && \
   [ $VECTOR_AGENT_RESULT -eq 0 ] && [ $GRAPH_AGENT_RESULT -eq 0 ] && [ $ROUTING_RESULT -eq 0 ]; then
    echo -e "${GREEN}All tests passed! Production ready.${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Review failures above.${NC}"
    exit 1
fi
