"""
Tests for the BM25 side of HybridSearchEngine.

The keyword index is built in memory from the collection, so a new engine
must reflect added, updated and removed documents. These tests use a real
ChromaDB collection with fake embeddings (no model download).
"""
import pytest
from langchain.schema import Document

from tests.conftest import _fake_vector
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.vector_store import initialize_chroma_db, index_documents


def doc(text, domain):
    return Document(page_content=text, metadata={"domain": domain, "source": "t"})


@pytest.fixture
def collection(tmp_path, fake_embeddings):
    _, col = initialize_chroma_db(str(tmp_path / "chroma"))
    index_documents(col, [
        doc("CAN bus carries frames between ECUs", "automotive"),
        doc("OBD-II exposes diagnostic trouble codes", "automotive"),
        doc("red cotton dress with floral print", "products"),
    ])
    return col


def ids_for(engine, query, domain=None):
    return [r["document"] for r in engine.bm25_search(query, 5, domain)]


def test_finds_existing_documents(collection):
    engine = HybridSearchEngine(collection)
    assert "CAN bus carries frames between ECUs" in ids_for(engine, "CAN frames")


def test_domain_filter(collection):
    engine = HybridSearchEngine(collection)
    results = engine.bm25_search("dress diagnostic", 5, domain="products")
    assert results
    assert all(r["metadata"]["domain"] == "products" for r in results)


def test_new_engine_sees_added_document(collection, fake_embeddings):
    old = HybridSearchEngine(collection)
    index_documents(collection, [doc("torque converter in automatic gearbox", "automotive")])
    assert not any("torque" in d for d in ids_for(old, "torque converter"))
    new = HybridSearchEngine(collection)
    assert any("torque" in d for d in ids_for(new, "torque converter"))


def test_new_engine_forgets_deleted_domain(collection):
    collection.delete(where={"domain": "products"})
    engine = HybridSearchEngine(collection)
    assert engine.bm25_search("dress", 5, domain="products") == []
    assert not any("dress" in d for d in ids_for(engine, "dress"))


def test_new_engine_sees_updated_content(collection):
    target = collection.get(where={"domain": "products"})
    new_text = "leather boots with steel toe"
    collection.update(ids=target["ids"], documents=[new_text],
                      embeddings=[_fake_vector(new_text)])
    engine = HybridSearchEngine(collection)
    assert any("boots" in d for d in ids_for(engine, "boots"))
    assert not any("dress" in d for d in ids_for(engine, "floral dress"))


def test_empty_collection_returns_no_results(tmp_path, fake_embeddings):
    _, empty = initialize_chroma_db(str(tmp_path / "empty"))
    engine = HybridSearchEngine(empty)
    assert engine.bm25_search("anything", 5) == []


def test_no_index_file_is_written(collection, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    HybridSearchEngine(collection)
    assert not list(tmp_path.glob("*.pkl"))
