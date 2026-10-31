"""
Document and query embeddings must come from the same model.

Documents are embedded with sentence-transformers (rag.retrieval.embeddings)
and stored as explicit vectors. A collection created without an embedding
function gets ChromaDB's own default (a separate ONNX copy of MiniLM), which
is used whenever a query is passed as text. These tests make sure no query
goes through that default. The vectors are fake, so they check wiring, not
model quality.
"""
import re
from pathlib import Path

import numpy as np
import pytest
from langchain.schema import Document

from rag.retrieval import embeddings
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.vector_store import index_documents, initialize_chroma_db
from tests.conftest import _fake_vector

ROOT = Path(__file__).resolve().parent.parent


class RecordingCollection:
    """Wraps a real collection and records the arguments of query()."""

    def __init__(self, inner):
        self.inner = inner
        self.query_calls = []

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self.inner.query(**kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


@pytest.fixture
def collection(tmp_path, fake_embeddings):
    _, col = initialize_chroma_db(str(tmp_path / "chroma"))
    index_documents(col, [
        Document(page_content="can bus frames", metadata={"domain": "auto"}),
        Document(page_content="obd trouble codes", metadata={"domain": "auto"}),
        Document(page_content="red cotton dress", metadata={"domain": "shop"}),
    ])
    return col


def test_semantic_search_sends_query_vector_not_query_text(collection):
    recording = RecordingCollection(collection)
    HybridSearchEngine(recording).semantic_search("can bus frames", n_results=2)

    assert len(recording.query_calls) == 1
    call = recording.query_calls[0]
    assert "query_texts" not in call
    assert call["query_embeddings"] == [_fake_vector("can bus frames")]


def test_hybrid_search_uses_the_document_embedder_for_queries(collection):
    recording = RecordingCollection(collection)
    HybridSearchEngine(recording).search("obd trouble codes", n_results=2, method="hybrid")
    assert recording.query_calls
    assert all("query_texts" not in call for call in recording.query_calls)


def test_query_vector_equals_stored_document_vector(collection):
    stored = collection.get(where={"domain": "shop"}, include=["embeddings", "documents"])
    assert stored["documents"] == ["red cotton dress"]
    assert list(stored["embeddings"][0]) == pytest.approx(_fake_vector("red cotton dress"))

    # Searching with a document's own text finds that document at distance zero.
    best = HybridSearchEngine(collection).semantic_search("red cotton dress", n_results=1)[0]
    assert best["document"] == "red cotton dress"
    assert best["distance"] == pytest.approx(0.0, abs=1e-6)


def test_domain_filter_still_applies_to_semantic_search(collection):
    results = HybridSearchEngine(collection).semantic_search("can bus", 5, domain="shop")
    assert [r["document"] for r in results] == ["red cotton dress"]


def test_no_code_path_queries_by_text():
    """Guard against reintroducing query_texts, which would use ChromaDB's default embedder."""
    offenders = []
    for folder in ("rag", "api", "scripts"):
        for path in (ROOT / folder).rglob("*.py"):
            if re.search(r"query_texts\s*=", path.read_text()):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


class RecordingModel:
    """Stands in for the SentenceTransformer and records encode() calls."""

    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(kwargs)
        if isinstance(texts, str):
            return np.array(_fake_vector(texts))
        return np.array([_fake_vector(t) for t in texts])


def test_single_and_batch_embedding_use_the_same_model_and_settings(monkeypatch):
    model = RecordingModel()
    monkeypatch.setattr(embeddings, "_model", model)

    single = embeddings.create_embedding("brake pads")
    batch = embeddings.create_embeddings_batch(["brake pads"])

    assert single == batch[0]
    # Only the progress bar flag may differ between the two code paths.
    single_kwargs, batch_kwargs = model.calls
    single_kwargs.pop("show_progress_bar", None)
    batch_kwargs.pop("show_progress_bar", None)
    assert single_kwargs == batch_kwargs
