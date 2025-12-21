# FlexiRAG - Dynamic Multi-Domain RAG Framework

![Tests](https://github.com/miraccanince/FlexiRAG/actions/workflows/tests.yml/badge.svg)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 37 passed](https://img.shields.io/badge/tests-37%20passed-brightgreen.svg)](tests/)

A flexible, production-ready RAG (Retrieval-Augmented Generation) framework that automatically adapts to any domain. Perfect for companies wanting to deploy RAG systems with their own documents - zero code changes required.

## What Makes This Different?

**True Framework Design:**
- Auto-discovers domains from your `data/` folder structure
- Zero code changes when adding new domains or documents
- Works with ANY company's data - just drop files in folders
- Production-ready with smart indexing and domain filtering
- 100% free and local - no API costs

**Current Status:** Production-ready with CI/CD, automated testing, and user feedback system

## Features

### Core Framework
- Dynamic multi-domain architecture
- Automatic domain detection from folder structure
- Multi-format support (PDF, CSV)
- Smart indexing with change detection
- Domain filtering for precise queries
- Interactive CLI with commands (/switch, /stats, /help)

### ML/AI Stack
- Local embeddings (sentence-transformers: all-MiniLM-L6-v2)
- Vector database (ChromaDB) with persistent storage
- Local LLM (Ollama + Llama 3.2 3B)
- Hybrid search (Semantic + BM25)
- LLM-based query reranking
- Semantic search with source citations
- 100% free and local (zero API costs)

### Production Features
- FastAPI backend with streaming responses
- Modern Streamlit web UI with analytics
- User feedback system (thumbs up/down with analytics)
- Performance optimization & caching (360x speedup)
- CI/CD pipeline with GitHub Actions
- 37 unit tests (100% pass rate, 81% coverage)
- Docker deployment
- Comprehensive documentation

### Current Dataset
- Automotive: 635 chunks (CAN, OBD-II, Infotainment PDFs)
- Fashion: 30,758 products (E-commerce CSV)
- Total: 31,393 indexed documents

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI (REST API)
- LangChain (RAG orchestration)
- ChromaDB (vector store)
- Sentence Transformers (all-MiniLM-L6-v2)
- Ollama + Llama 3.2 3B
- BM25 (keyword search)

**Frontend:**
- Streamlit (web UI)
- Plotly (interactive charts)

**Testing & CI/CD:**
- Pytest (37 unit tests, 100% pass rate)
- pytest-cov (81% coverage on core modules)
- GitHub Actions (automated testing on every push/PR)

**Deployment:**
- Docker & Docker Compose
- Uvicorn (ASGI server)

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) (for local LLM)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/miraccanince/FlexiRAG.git
   cd FlexiRAG
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Ollama and download model:**
   ```bash
   # macOS
   brew install ollama

   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh

   # Download model
   ollama pull llama3.2:3b
   ```

5. **Add your documents:**
   ```bash
   # Create domain folders and add your documents
   mkdir -p data/your_domain
   cp your_files.pdf data/your_domain/
   ```

6. **Index documents:**
   ```bash
   python index_documents.py
   ```

## Usage

### Web Interface (Recommended)

Start API and frontend:

**Terminal 1 - Start API:**
```bash
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 - Start Frontend:**
```bash
streamlit run frontend/app.py
```

Then open:
- **Web UI:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

### Command Line Interface

```bash
python main.py
```

Available commands:
```
/switch   # Change domain
/stats    # View statistics
/help     # Show help
/quit     # Exit
```

### Docker Deployment

```bash
docker-compose up -d
```

Access services:
- Frontend: http://localhost:8501
- API: http://localhost:8000

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## Project Structure

```
FlexiRAG/
├── src/                          # Core source code
│   ├── pdf_loader.py            # PDF loading and chunking
│   ├── csv_loader.py            # CSV data processing
│   ├── embeddings.py            # Embedding generation
│   ├── vector_store.py          # ChromaDB operations
│   ├── qa_chain.py              # RAG pipeline
│   ├── hybrid_search.py         # Hybrid search (Semantic + BM25)
│   ├── reranker.py              # LLM-based reranking
│   ├── cache_manager.py         # Query caching & performance
│   └── feedback_manager.py      # User feedback system
├── api/                          # FastAPI backend
│   └── main.py                  # REST API endpoints
├── frontend/                     # Streamlit frontend
│   └── app.py                   # Web UI
├── tests/                        # Unit tests (37 tests)
│   ├── test_embeddings.py       # Embedding tests
│   ├── test_vector_store.py     # Vector store tests
│   ├── test_cache_manager.py    # Cache tests
│   ├── test_csv_loader.py       # CSV loader tests
│   └── test_feedback_manager.py # Feedback tests
├── .github/workflows/            # CI/CD
│   └── tests.yml                # GitHub Actions workflow
├── data/                         # Document storage
│   ├── automotive/              # Domain 1
│   └── fashion/                 # Domain 2
├── feedback/                     # User feedback data
│   └── feedback_store.json      # Feedback storage
├── chroma_db/                    # Vector database (auto-generated)
├── main.py                       # CLI interface
├── index_documents.py            # Document indexing script
├── requirements.txt              # Python dependencies
└── docker-compose.yml            # Docker configuration
```

## API Endpoints

**Query & Search:**
- `POST /query` - Question answering with LLM (streaming)
- `POST /search` - Document search without LLM
- `GET /domains` - List available domains
- `GET /health` - System health check

**Feedback:**
- `POST /feedback` - Submit user feedback
- `GET /feedback/stats` - Get feedback analytics

**Management:**
- `POST /upload` - Upload new documents
- `DELETE /domain/{name}` - Delete domain

Full API documentation: http://localhost:8000/docs

## Example Queries

**Automotive:**
- "What is CAN protocol used for?"
- "How does OBD-II diagnostic work?"
- "Explain infotainment system architecture"

**Fashion (E-commerce):**
- "Show me dresses under 1000 rupees"
- "What brands sell western wear?"
- "Find jewellery products"

## Documentation

- [FEEDBACK_SYSTEM.md](FEEDBACK_SYSTEM.md) - User feedback system implementation
- [CI_CD_GUIDE.md](CI_CD_GUIDE.md) - CI/CD pipeline guide
- [tests/README.md](tests/README.md) - Testing documentation

## Development

### Adding New Domains

1. Create folder in `data/`:
   ```bash
   mkdir data/new_domain
   ```

2. Add documents (PDF or CSV):
   ```bash
   cp documents.pdf data/new_domain/
   ```

3. Reindex:
   ```bash
   python index_documents.py
   ```

The system automatically detects and indexes the new domain.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Submit a pull request

CI/CD pipeline will automatically run tests on your PR.

## Performance

- Average query time: 3.6s (with caching: ~0.01s)
- Cache hit rate: ~85% in production use
- Speedup with caching: 360x
- Index size: 31,393 documents
- Coverage: 81% on core modules

## License

MIT License - See LICENSE file for details

## Author

**Mirac Can Ince**

Portfolio project demonstrating production-ready RAG systems for ML Engineer positions.

Built using Python, ChromaDB, and Llama 3.2 | 100% Free & Local
