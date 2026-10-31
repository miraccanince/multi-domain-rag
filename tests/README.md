# Tests

Run from the repository root:

```bash
pytest tests/ -v
pytest tests/ --cov=rag --cov-report=term
```

`pytest.ini` puts the repository root on the import path. `conftest.py` points `RAG_STORAGE_DIR` at a temporary directory, so the tests never read or write your real `storage/` data.

## Files

| File | Covers | Needs the embedding model |
|------|--------|---------------------------|
| test_auth.py | user store, bcrypt hashing, JWT creation and verification, secret handling (environment variable, generated file, restart stability) | no |
| test_cache_manager.py | exact-match cache: get/set, LRU eviction, TTL, statistics | no |
| test_semantic_cache.py | semantic cache with hand-written vectors: hit and miss at the 0.85 threshold, domain filter, retrieval-settings key, eviction, persistence | no |
| test_feedback_manager.py | feedback storage, statistics, CSV and JSON export, date filters | no |
| test_csv_loader.py | CSV to documents, column detection, domain metadata, domain filter in ChromaDB | no |
| test_hybrid_search.py | BM25 index after documents are added, updated and deleted | no |
| test_embedding_consistency.py | queries are embedded with the document embedder and never sent to Chroma as text | no |
| test_pipeline.py | `ask_question` over the example PDF and CSV: sources, domain filter for each search method, reranking and its fallbacks, no-result and unknown-domain queries, prompt limits, Ollama failure | no |
| test_api_pipeline.py | `/query`, `/search`, `/domains` on a real collection: streaming and non-streaming parity, no-result and failure handling, collection changed outside the API, cache key | no |
| test_source_display.py | sources show a file name without directories and PDF pages from 1; stored metadata is unchanged | no |
| test_cli.py | `scripts.chat_cli` with scripted input | no |
| test_eval_metrics.py, test_eval_questions.py | the evaluation metrics, the question file against the committed EPA snapshot, the held-out guard, and (if the NIST PDFs are downloaded) every gold span | no |
| test_frontend.py | the Streamlit script runs without exceptions on the installed Streamlit (headless runner, no browser) | no |
| test_api_query.py | `/query` with Ollama, embeddings and search faked: cache write after streaming, NDJSON replay on a cache hit, no caching of empty answers or LLM errors, cache clearing after document changes | no |
| test_examples.py | ingestion and keyword retrieval over the synthetic domains in `examples/` | no |
| test_embeddings.py | embedding shape and similarity | yes (all-MiniLM-L6-v2, downloaded on first run) |
| test_vector_store.py | ChromaDB indexing, search, domain filter | yes |

Tests that need a vector store use a real ChromaDB collection in a temporary directory with a deterministic fake embedding function (`fake_embeddings` in `conftest.py`). Tests that reach the LLM use `fake_ollama`, which records prompts and returns canned text. Both are mocks: no real language model runs in this suite, and the real sentence-transformers model runs only in the two files marked above.

## Not covered

`frontend/app.py`, real Ollama and sentence-transformers behavior, the upload and delete endpoints, and most of `scripts/index_documents.py` and `scripts/chat_cli.py`. Nothing here measures answer quality. The sample data in `examples/` is synthetic and tiny, so the example tests show that the pipeline runs, not that retrieval is good.
