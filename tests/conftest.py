"""
Pytest configuration and shared fixtures.
"""
import os
import tempfile
from pathlib import Path

import pytest

# Keep tests away from the real runtime state. This must run before any
# rag module is imported, because rag.config reads the environment at import time.
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["RAG_STORAGE_DIR"] = tempfile.mkdtemp(prefix="rag_test_storage_")


@pytest.fixture(scope="session")
def test_data_dir():
    """Directory for test data files."""
    return Path(__file__).parent / "test_data"


def pytest_configure(config):
    """Pytest configuration hook."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def _fake_vector(text, dim=32):
    """Deterministic bag-of-words vector, so tests need no embedding model."""
    import zlib
    vec = [0.0] * dim
    for word in text.lower().split():
        vec[zlib.crc32(word.encode()) % dim] += 1.0
    return vec


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Replace the sentence-transformers embeddings used by the vector store."""
    monkeypatch.setattr(
        "rag.retrieval.vector_store.create_embedding", _fake_vector)
    monkeypatch.setattr(
        "rag.retrieval.vector_store.create_embeddings_batch",
        lambda texts, batch_size=32: [_fake_vector(t) for t in texts])


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def example_index(tmp_path, fake_embeddings):
    """
    The example PDF and CSV indexed in a real ChromaDB collection (fake embeddings).

    Returns (client, collection, engine).
    """
    from rag.ingestion.csv_loader import load_all_csvs_from_directory
    from rag.ingestion.pdf_loader import load_pdfs_from_directory
    from rag.retrieval.hybrid_search import HybridSearchEngine
    from rag.retrieval.vector_store import index_documents, initialize_chroma_db

    docs = load_pdfs_from_directory(str(EXAMPLES_DIR / "automotive"), domain="automotive")
    docs += load_all_csvs_from_directory(str(EXAMPLES_DIR / "products"), domain="products")
    client, collection = initialize_chroma_db(str(tmp_path / "chroma"))
    index_documents(collection, docs)
    return client, collection, HybridSearchEngine(collection)


class FakeOllamaResponse:
    """Stands in for requests.Response for /api/generate."""
    status_code = 200

    def __init__(self, text):
        self.text = text

    def json(self):
        return {"response": self.text}

    def iter_lines(self, decode_unicode=True):
        import json
        yield json.dumps({"response": self.text, "done": False})
        yield json.dumps({"response": "", "done": True})


class FakeOllama:
    """Records every prompt sent to Ollama and answers rerank and generate calls."""

    def __init__(self):
        self.prompts = []
        self.rerank_reply = "1,2,3"
        self.answer = "Fake answer [Document 1]."
        self.down = False

    @property
    def generate_prompts(self):
        return [p for p in self.prompts if "relevance scoring expert" not in p]

    @property
    def rerank_prompts(self):
        return [p for p in self.prompts if "relevance scoring expert" in p]

    def post(self, url, json=None, **kwargs):
        import requests
        self.prompts.append(json["prompt"])
        if self.down:
            raise requests.exceptions.ConnectionError("ollama is down")
        if "relevance scoring expert" in json["prompt"]:
            return FakeOllamaResponse(self.rerank_reply)
        return FakeOllamaResponse(self.answer)


@pytest.fixture
def fake_ollama(monkeypatch):
    """Replace requests.post. This is a mock: no real language model runs."""
    fake = FakeOllama()
    monkeypatch.setattr("requests.post", fake.post)
    return fake
