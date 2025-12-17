# FlexiRAG - Dynamic Multi-Domain RAG Framework

A flexible, production-ready RAG (Retrieval-Augmented Generation) framework that automatically adapts to any domain. Perfect for companies wanting to deploy RAG systems with their own documents - zero code changes required!

## 🎯 What Makes This Different?

**True Framework Design:**
- 🔄 **Auto-discovers domains** from your `data/` folder structure
- 📁 **Zero code changes** when adding new domains or documents
- 🎨 **Works with ANY company's data** - just drop files in folders
- 🚀 **Production-ready** with smart indexing and domain filtering
- 💰 **100% free and local** - no API costs

**Current Status:** ✅ Week 2 Complete - Dynamic multi-domain framework with evaluation (75-85% accuracy)

## Project Overview

Portfolio project demonstrating advanced ML/RAG engineering for ML Engineer roles in Amsterdam/Randstad area.

## ✨ Features

**🎯 Core Framework (Week 1-2):**
- ✅ Dynamic multi-domain architecture
- ✅ Automatic domain detection from folder structure
- ✅ Multi-format support (PDF, CSV)
- ✅ Smart indexing with change detection
- ✅ Domain filtering for precise queries
- ✅ Interactive CLI with commands (/switch, /stats, /help)
- ✅ Custom evaluation framework (keyword coverage + success rate)

**🤖 ML/AI Stack:**
- ✅ Local embeddings (sentence-transformers: all-MiniLM-L6-v2)
- ✅ Vector database (ChromaDB) with persistent storage
- ✅ Local LLM (Ollama + Llama 3.2 3B)
- ✅ Semantic search with source citations
- ✅ 100% free and local (zero API costs)

**📊 Current Dataset:**
- ✅ Automotive: 635 chunks (CAN, OBD-II, Infotainment PDFs)
- ✅ Fashion: 30,758 products (E-commerce CSV)
- ✅ Total: 31,393 indexed documents

**🔜 Planned (Week 3-4):**
- Evaluation metrics (RAGAS framework)
- Hybrid search (semantic + keyword)
- Query reranking
- PCA visualization
- Streamlit UI
- Deployment guide

## Tech Stack

- Python 3.13
- LangChain (RAG orchestration)
- ChromaDB (vector store)
- Sentence Transformers (local embeddings - all-MiniLM-L6-v2)
- Ollama + Llama 3.2 (local LLM)
- PyPDF (PDF processing)

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) (for local LLM)

### Installation

1. Clone the repository

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Ollama and download model:
   ```bash
   brew install ollama  # macOS
   ollama pull llama3.2:3b
   ```

5. Place your PDF documents in `data/automotive/` directory

## 🚀 Quick Start

### 1. Add Your Documents

Simply organize your documents in the `data/` folder:

```bash
data/
├── automotive/        # Your PDFs here
│   ├── manual.pdf
│   └── specs.pdf
├── legal/             # Different domain
│   └── contracts.pdf
└── medical/           # Another domain
    └── research.pdf
```

**That's it!** The system auto-detects domains from folder names.

### 2. Run the System

```bash
python3 main.py
```

The system will:
- 🔍 Auto-detect all domains
- 💾 Prompt to index new documents (if needed)
- 📂 Let you select a domain
- 💬 Answer your questions with citations

### 3. Interactive Commands

```bash
💬 Your question: What is CAN protocol?
# Or use commands:
/switch   # Change domain
/stats    # View statistics
/help     # Show help
/quit     # Exit
```

### Example Queries by Domain

**Automotive:**
- "What is CAN protocol used for?"
- "How does OBD-II diagnostic work?"
- "Explain infotainment system architecture"

**Fashion (E-commerce):**
- "Show me dresses under 1000 rupees"
- "What brands sell western wear?"
- "Find jewellery products"

## Project Structure

```
RAGDocumentationAssistant/
├── src/
│   ├── pdf_loader.py        # PDF loading and chunking
│   ├── embeddings.py         # Local embedding generation
│   ├── vector_store.py       # ChromaDB operations
│   └── qa_chain.py           # RAG pipeline (retrieve + LLM)
├── data/
│   ├── automotive/           # PDF documents
│   └── ecommerce/            # CSV data (coming in Week 2)
├── notebooks/                # Jupyter experiments
│   ├── 01_pdf_loading_experiment.ipynb
│   └── 02_embedding_experiment.ipynb
├── chroma_db/                # Vector database (auto-generated)
├── main.py                   # Interactive Q&A interface
├── index_documents.py        # Document indexing script
└── requirements.txt          # Python dependencies
```

## Current Dataset

- **Automotive Documentation:**
  - CAN.pdf (167 pages) - Controller Area Network protocol
  - On-board Diagnostics.pdf (20 pages) - OBD-II standards
  - automotive_infotainment.pdf (62 pages) - Infotainment systems
  - **Total:** 635 chunks indexed

## 📅 Development Roadmap

**✅ Week 1: Foundation (Complete)**
- PDF loading and chunking
- Local embeddings (sentence-transformers)
- ChromaDB vector store
- Ollama LLM integration
- Interactive CLI interface

**✅ Week 2: Framework Architecture (Complete)**
- Dynamic multi-domain detection
- CSV support for structured data
- Smart indexing with change detection
- Domain filtering system
- Multi-format document processing

**🔜 Week 3: Advanced Features**
- RAGAS evaluation metrics
- Hybrid search (semantic + keyword)
- Query reranking
- PCA visualization for embeddings
- Performance optimization

**🔜 Week 4: Production & UI**
- Streamlit web interface
- Docker containerization
- API endpoints
- Deployment guide
- Documentation

## Author

Building this to transition from QA Engineer to ML Engineer in Netherlands.
