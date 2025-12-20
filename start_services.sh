#!/bin/bash

# RAG Documentation Assistant - Service Starter
# This script starts both the FastAPI backend and Streamlit frontend

set -e

echo "🚀 Starting RAG Documentation Assistant..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Ollama is running
echo -n "Checking Ollama service... "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    echo ""
    echo "Please start Ollama first:"
    echo "  ollama serve"
    exit 1
fi

# Check if ChromaDB exists
if [ ! -d "chroma_db" ]; then
    echo -e "${RED}✗ ChromaDB not found${NC}"
    echo "Please index documents first:"
    echo "  python index_documents.py"
    exit 1
fi

echo -e "${GREEN}✓ ChromaDB found${NC}"
echo ""

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Shutting down services..."
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "✓ Services stopped"
    exit 0
}

trap cleanup INT TERM

# Start FastAPI backend
echo -e "${BLUE}Starting FastAPI backend...${NC}"
./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/rag-api.log 2>&1 &
API_PID=$!
echo "  PID: $API_PID"
echo "  Logs: /tmp/rag-api.log"

# Wait for API to be ready
echo -n "  Waiting for API to start"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Check API health
API_HEALTH=$(curl -s http://localhost:8000/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
if [ "$API_HEALTH" = "healthy" ]; then
    echo -e "  Status: ${GREEN}Healthy${NC}"
else
    echo -e "  Status: ${RED}$API_HEALTH${NC}"
fi

echo ""

# Start Streamlit frontend
echo -e "${BLUE}Starting Streamlit frontend...${NC}"
./venv/bin/streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 > /tmp/rag-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"
echo "  Logs: /tmp/rag-frontend.log"

# Wait for frontend to be ready
echo -n "  Waiting for frontend to start"
for i in {1..30}; do
    if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Display access information
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ All services started successfully!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access URLs:"
echo "  📱 Frontend UI:    http://localhost:8501"
echo "  🔧 API Backend:    http://localhost:8000"
echo "  📚 API Docs:       http://localhost:8000/docs"
echo "  ❤️  Health Check:  http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running
wait
