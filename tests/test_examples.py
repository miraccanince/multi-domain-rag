"""
Ingestion and keyword retrieval over the synthetic sample domains in examples/.

The data is made up and tiny. These tests check that the pipeline works end to
end (discovery, loading, indexing, domain filtering, BM25 retrieval). They say
nothing about answer quality. Embeddings are faked, so no model is needed.
"""
from pathlib import Path

import pytest

from rag.ingestion.csv_loader import load_all_csvs_from_directory
from rag.ingestion.pdf_loader import load_pdfs_from_directory
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.vector_store import (
    get_available_domains, index_documents, initialize_chroma_db)
from scripts.index_documents import discover_domains

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_domains_are_discovered_from_folders():
    domains = discover_domains(EXAMPLES)
    assert set(domains) == {"automotive", "products"}
    assert domains["automotive"]["pdfs"] == 1
    assert domains["products"]["csvs"] == 1


@pytest.fixture
def engine(tmp_path, fake_embeddings):
    docs = load_pdfs_from_directory(str(EXAMPLES / "automotive"), domain="automotive")
    docs += load_all_csvs_from_directory(str(EXAMPLES / "products"), domain="products")
    _, collection = initialize_chroma_db(str(tmp_path / "chroma"))
    index_documents(collection, docs)
    assert get_available_domains(collection) == {"automotive": 2, "products": 30}
    return HybridSearchEngine(collection)


def test_pdf_query_finds_the_right_page(engine):
    results = engine.bm25_search("CAN bus arbitration error frame", 3, domain="automotive")
    assert results[0]["metadata"]["source"].endswith("vehicle_diagnostics.pdf")
    assert results[0]["metadata"]["page"] == 0
    assert "Controller Area Network" in results[0]["document"]


def test_csv_query_finds_matching_products(engine):
    results = engine.bm25_search("waterproof", 2, domain="products")
    names = {r["metadata"]["name"] for r in results}
    assert names == {"Rain Jacket", "Waterproof Hiking Boots"}


def test_domain_filter_keeps_domains_apart(engine):
    results = engine.bm25_search("waterproof boots brake pads", 10, domain="automotive")
    assert results
    assert all(r["metadata"]["domain"] == "automotive" for r in results)
