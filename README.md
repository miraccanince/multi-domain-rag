# Multi-Domain RAG

A retrieval-augmented generation (RAG) application that answers questions about PDFs and CSV files from several domains, using local embeddings, search and a local language model.

## Overview

Documents such as technical manuals and product catalogs come in different formats, and a general-purpose chat model cannot see them. This project indexes them into one shared pipeline, with each top-level folder under `data/` treated as a domain. A question can be limited to one domain or asked across all of them. Answers are generated only from the retrieved text and list the source file and page or row. Embeddings, vector search and the language model all run locally, so no document text is sent to an external API.

## Features

- Ingestion of PDFs (chunked, with file and page kept) and CSV files (one document per row), tagged by domain.
- Hybrid retrieval that combines vector search and BM25 keyword search with Reciprocal Rank Fusion, with an optional domain filter.
- Optional reranking of candidates with the local language model.
- Streamed answers with cited sources, served by a FastAPI backend, a Streamlit UI and a command-line chat.
- A semantic cache for repeated questions, JWT-based user accounts and a feedback store.

## Architecture

```
 data/<domain>/*.pdf, *.csv
        |  python -m scripts.index_documents  (or POST /upload)
        v
 chunk -> embed (all-MiniLM-L6-v2) -> ChromaDB collection

 question (UI, API or CLI)
        |
        v
 semantic cache lookup ---- hit: replay stored answer
        | miss
        v
 hybrid retrieval: vector search + BM25 -> Reciprocal Rank Fusion
        |
        v
 rerank candidates with the local LLM (optional), keep top 3
        |
        v
 Ollama (llama3.2:3b) answers from the retrieved chunks
        |
        v
 answer + sources (file, page or row)
```

- **Ingestion** ([rag/ingestion/](rag/ingestion/), [scripts/index_documents.py](scripts/index_documents.py)): PDFs are split into 1000-character chunks with 200 characters of overlap. CSV rows become documents from their text columns.
- **Retrieval** ([rag/retrieval/hybrid_search.py](rag/retrieval/hybrid_search.py)): the BM25 index is built in memory from the collection. The API rebuilds it and clears the caches when the collection changes.
- **Reranking** ([rag/retrieval/reranker.py](rag/retrieval/reranker.py)): prompt-based ranking with the same local model, not a trained cross-encoder. If it fails, the retrieval order is kept.
- **Generation** ([rag/qa_chain.py](rag/qa_chain.py)): the prompt tells the model to answer only from the context and to say so when it cannot. Answers are capped at 150 tokens.
- **Backend and UI** ([api/main.py](api/main.py), [frontend/app.py](frontend/app.py)): `/query`, `/search`, `/upload`, `/auth/*` and other endpoints, plus a Streamlit app with chat, analytics and management tabs.

## Tech Stack

- **Language and serving:** Python 3.12+, FastAPI, Uvicorn, Streamlit, Plotly
- **Retrieval:** ChromaDB, sentence-transformers (`all-MiniLM-L6-v2`), rank-bm25
- **Generation:** Ollama with `llama3.2:3b`
- **Document loading:** LangChain loaders and text splitter, pypdf, pandas
- **Security and limits:** python-jose (JWT), bcrypt, slowapi (rate limiting)
- **Quality and delivery:** pytest, GitHub Actions, Docker, GitHub Container Registry

## Getting Started

**Prerequisites:** Python 3.12 or newer, and [Ollama](https://ollama.com/) running on port 11434. The first install downloads PyTorch, and the first run downloads the embedding model.

```bash
git clone https://github.com/miraccanince/multi-domain-rag.git
cd multi-domain-rag
python3 -m venv venv
source venv/bin/activate
pip install .
ollama pull llama3.2:3b
```

Index the two sample domains in `examples/` (or put your own PDFs and CSVs in one folder per domain under `data/`):

```bash
mkdir -p data
cp -r examples/automotive examples/products data/
python -m scripts.index_documents --yes
```

Start the API and the UI in two terminals:

```bash
uvicorn api.main:app --port 8000              # http://localhost:8000/docs
python -m streamlit run frontend/app.py       # http://localhost:8501
```

Register an account in the UI before using the chat tab. For a terminal chat, run `python -m scripts.chat_cli`.

**Configuration.** Settings in [rag/config.py](rag/config.py) can be overridden with environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAG_DATA_DIR` | `./data` | one subfolder per domain |
| `RAG_STORAGE_DIR` | `./storage` | ChromaDB, users, caches, feedback |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `LLM_MODEL` | `llama3.2:3b` | model for reranking and answers |
| `API_URL` | `http://localhost:8000` | API address used by the UI |
| `JWT_SECRET` | generated | token signing secret |

**Docker.** `docker compose up --build` runs the API and UI with Ollama on the host (see [docker-compose.yml](docker-compose.yml)). CI also publishes the API image to GitHub Container Registry after tests pass on `main`:

```bash
docker pull ghcr.io/miraccanince/multi-domain-rag:latest
docker run -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  --add-host=host.docker.internal:host-gateway \
  -v $(pwd)/data:/app/data -v $(pwd)/storage:/app/storage \
  ghcr.io/miraccanince/multi-domain-rag:latest
```

The image contains only the application. Ollama and the model must be run separately and be reachable at `OLLAMA_URL`. I have not run the container locally.

## Example Usage

Domain `automotive`, question "What is a CAN error frame?", answered by `llama3.2:3b` in the Streamlit UI:

> A CAN error frame is sent by a node when it detects an error. When a node with repeated errors moves to the error passive state and finally goes bus off, it sends an error frame (Document 1). The purpose of the error frame is to alert other nodes on the network to potential issues.

Source: `vehicle_diagnostics.pdf`, page 1. Wording varies between runs because the answer is generated.

![Chat tab with a question, the generated answer and its cited source](docs/images/app-screenshot.png)

## Evaluation

Retrieval was measured on 25 answerable questions: 15 about four NIST documents (253 pages, 797 chunks) and 6 about 2,607 EPA vehicle records, plus 4 vehicle questions that need counts or averages and are reported separately in the raw output. One run on 31 October 2026, using the application's own ingestion. Recall is the share of gold evidence spans covered by the top k chunks, and precision is the share of the top k rows that match the gold rows. Reranking takes 9 hybrid candidates and keeps 3.

| Configuration | Docs recall@1 | Docs recall@3 | Docs MRR@3 | Vehicles precision@3 | Vehicles MRR@3 | Median latency, docs / vehicles (ms) |
|---------------|------|------|------|------|------|-------------|
| BM25 | 0.33 | 0.45 | 0.40 | 0.78 | 0.83 | 3 / 9 |
| Vector | 0.27 | 0.28 | 0.30 | 0.17 | 0.31 | 14 / 235 |
| Hybrid | 0.15 | 0.55 | 0.39 | 0.39 | 0.50 | 17 / 193 |
| Hybrid + rerank | 0.20 | 0.53 | 0.33 | 0.67 | 0.64 | 1,100 / 1,481 |

- **Documents:** hybrid search had the best recall@3 (0.55), ahead of BM25 (0.45) and vector (0.28), while BM25 had the best recall@1 and MRR@3. Reranking with the 3B model (0.53) did not improve on hybrid and added about one second per query.
- **Vehicle rows:** BM25 was clearly best (precision@3 0.78) and vector search was weakest (0.17). The indexed row text is a short list of `name: value` lines. Hybrid (0.39) fell between them. Reranking raised hybrid to 0.67 but stayed below BM25 alone.
- With 15 and 6 questions, one question moves a mean by 0.07 and 0.17, so most gaps are within noise. No confidence intervals were computed.
- This is one run. Answer quality was not evaluated, and the results describe these documents only.

Question set, ground truth and metric definitions are in [eval/README.md](eval/README.md), data sources in [eval/SOURCES.md](eval/SOURCES.md), and the raw output with per-question rankings in [eval/results/retrieval_all_20261031T221011.json](eval/results/retrieval_all_20261031T221011.json).

## Testing

```bash
pytest tests/ -v
```

All 230 tests passed in 37 seconds on a local run with Python 3.13, and CI runs the same suite on every push and pull request. Most tests use fake embeddings and a fake Ollama client, with real ChromaDB, BM25, caches and FastAPI routes. Two files load the real embedding model, so the first run needs network access. A separate run on the sample domains with real embeddings and Ollama covered indexing, streaming and non-streaming answers, refusals, caching, upload and delete. See [tests/README.md](tests/README.md) for details.

## Limitations

- **Reranking is unreliable with the 3B model.** In smoke tests it dropped the correct PDF chunk when no domain filter was set. It is on by default in the API, and turning it off is a reasonable choice.
- **CSV numbers are not searchable.** Only text columns go into the document text, so questions that need counts, maxima or numeric thresholds cannot be answered reliably.
- **Minimal access control and storage.** Registration is open, `/query` needs no token, and CORS allows all origins. Users, feedback and the semantic cache are JSON files, suitable for one process only. Password hashes committed early in the history should be treated as compromised.
- **Narrow evaluation.** Retrieval was measured on a small question set. Answer quality, cache hit rates on real paraphrases and load were not measured, and the repository has no license file.
