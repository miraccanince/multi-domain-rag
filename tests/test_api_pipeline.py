"""
/query, /search and /domains against a real ChromaDB collection.

MOCKED: embeddings (fake vectors) and Ollama (FakeOllama). REAL: ChromaDB,
BM25, fusion, prompt and source building, the NDJSON protocol, cache logic.
"""
import json

import pytest
from fastapi.testclient import TestClient
from langchain.schema import Document

import api.main as api_main
from rag import config
from rag.caching.semantic_cache import SemanticCache
from rag.qa_chain import NO_ANSWER, LLM_ERROR_PREFIX
from rag.retrieval.vector_store import index_documents
from tests.conftest import _fake_vector


@pytest.fixture
def api(example_index, fake_ollama, tmp_path, monkeypatch):
    client, collection, engine = example_index
    cache = SemanticCache(cache_file=tmp_path / "semantic.json")
    monkeypatch.setattr(api_main, "chroma_client", client)
    monkeypatch.setattr(api_main, "collection", collection)
    monkeypatch.setattr(api_main, "hybrid_engine", engine)
    monkeypatch.setattr(api_main, "create_embedding", _fake_vector)
    monkeypatch.setattr(api_main, "get_semantic_cache", lambda: cache)
    monkeypatch.setattr(api_main.limiter, "enabled", False)
    test_client = TestClient(api_main.app)
    test_client.chroma = client
    test_client.cache = cache
    test_client.ollama = fake_ollama
    return test_client


def query(api, question, **overrides):
    body = {"question": question, "search_method": "bm25", "use_reranking": False,
            "use_cache": False, "stream": False}
    body.update(overrides)
    return api.post("/query", json=body)


def stream_events(response):
    return [json.loads(line) for line in response.text.splitlines() if line]


# ---- streaming and non-streaming agree -----------------------------------

@pytest.mark.parametrize("question,domain", [
    ("What is a CAN error frame?", "automotive"),
    ("waterproof", "products"),
])
def test_streaming_and_non_streaming_return_the_same_sources(api, question, domain):
    plain = query(api, question, domain=domain).json()
    events = stream_events(query(api, question, domain=domain, stream=True))
    done = events[-1]

    assert done["type"] == "done"
    assert done["sources"] == plain["sources"]
    assert done["answer"] == plain["answer"]
    assert plain["sources"]


def test_streaming_marks_cited_sources_like_non_streaming(api):
    api.ollama.answer = "Only Document 2 is relevant."
    plain = query(api, "waterproof", domain="products", search_method="hybrid").json()
    done = stream_events(query(api, "waterproof", domain="products",
                               search_method="hybrid", stream=True))[-1]
    assert [s["cited"] for s in plain["sources"]] == [False, True, False]
    assert [s["cited"] for s in done["sources"]] == [False, True, False]


def test_both_modes_send_the_same_prompt(api):
    query(api, "waterproof", domain="products")
    query(api, "waterproof", domain="products", stream=True)
    first, second = api.ollama.generate_prompts
    assert first == second


# ---- empty and failing cases ---------------------------------------------

def test_no_results_non_streaming(api):
    response = query(api, "zebra quantum")
    assert response.status_code == 200
    assert response.json()["answer"] == NO_ANSWER
    assert response.json()["sources"] == []
    assert api.ollama.prompts == []


def test_no_results_streaming(api):
    events = stream_events(query(api, "zebra quantum", stream=True))
    assert [e["type"] for e in events] == ["metadata", "token", "done"]
    assert events[-1]["answer"] == NO_ANSWER
    assert api.ollama.prompts == []


def test_unknown_domain_returns_no_answer(api):
    response = query(api, "waterproof", domain="missing", search_method="hybrid")
    assert response.status_code == 200
    assert response.json()["answer"] == NO_ANSWER


def test_streaming_reports_llm_failure_and_does_not_cache(api):
    api.ollama.down = True
    response = query(api, "What is a CAN error frame?", domain="automotive",
                     stream=True, use_cache=True)
    events = stream_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"].startswith(LLM_ERROR_PREFIX)
    assert events[-1]["sources"]
    assert api.cache.cache == {}


def test_search_endpoint_returns_sources_without_the_llm(api):
    response = api.post("/search", json={"query": "floral dress", "domain": "products",
                                         "search_method": "bm25", "n_results": 2})
    assert response.status_code == 200
    assert "Floral Summer Dress" in response.json()["results"][0]["document"]
    assert api.ollama.prompts == []


# ---- the collection changes outside this process ---------------------------

def recreate_collection(api, texts):
    api.chroma.delete_collection(config.COLLECTION_NAME)
    fresh = api.chroma.create_collection(config.COLLECTION_NAME)
    index_documents(fresh, [Document(page_content=t, metadata={"domain": "new", "source": "n.pdf",
                                                              "source_type": "pdf", "page": 0})
                            for t in texts])
    return fresh


def test_recreated_collection_is_picked_up(api):
    recreate_collection(api, ["spark plug gap is set with a feeler gauge"])

    response = query(api, "spark plug gauge")
    assert response.status_code == 200
    assert response.json()["sources"][0]["source"] == "n.pdf"
    assert api.get("/domains").json()["domains"][0]["name"] == "new"


def test_documents_added_outside_the_api_are_picked_up(api):
    index_documents(api_main.collection, [Document(
        page_content="torque converter locks up at cruising speed",
        metadata={"domain": "automotive", "source": "extra.pdf", "source_type": "pdf", "page": 3})])

    response = query(api, "torque converter", domain="automotive")
    assert response.json()["sources"][0]["source"] == "extra.pdf"


def test_refresh_clears_cached_answers(api):
    query(api, "What is a CAN error frame?", domain="automotive", use_cache=True, stream=True)
    assert api.cache.cache
    recreate_collection(api, ["something else entirely"])
    query(api, "something else")
    assert api.cache.cache == {}


# ---- semantic cache respects retrieval settings -----------------------------

def test_cached_answer_is_not_reused_with_different_settings(api):
    ask = dict(domain="automotive", use_cache=True, stream=True)
    query(api, "What is a CAN error frame?", n_results=3, **ask)
    assert len(api.ollama.generate_prompts) == 1

    query(api, "What is a CAN error frame?", n_results=3, **ask)   # same settings: hit
    assert len(api.ollama.generate_prompts) == 1

    query(api, "What is a CAN error frame?", n_results=1, **ask)   # other n_results: miss
    assert len(api.ollama.generate_prompts) == 2

    query(api, "What is a CAN error frame?", n_results=3, search_method="hybrid", **ask)
    assert len(api.ollama.generate_prompts) == 3

    query(api, "What is a CAN error frame?", n_results=3, use_reranking=True, **ask)
    assert len(api.ollama.generate_prompts) == 4


# ---- sources show file names and 1-based pages ------------------------------

def test_query_sources_have_no_directories_and_pages_start_at_one(api):
    sources = query(api, "What is a CAN error frame?", domain="automotive").json()["sources"]
    assert sources
    for source in sources:
        assert "/" not in source["source"] and "\\" not in source["source"]
    assert sources[0]["source"] == "vehicle_diagnostics.pdf"
    assert sources[0]["page"] == 1  # the first PDF page is stored as 0


@pytest.mark.parametrize("method", ["bm25", "semantic"])
def test_search_results_have_no_directories_and_pages_start_at_one(api, method):
    response = api.post("/search", json={"query": "CAN error frame", "domain": "automotive",
                                         "search_method": method, "n_results": 2})
    assert response.status_code == 200
    for result in response.json()["results"]:
        assert result["metadata"]["source"] == "vehicle_diagnostics.pdf"
        assert result["metadata"]["page"] >= 1


def test_streamed_sources_have_no_directories(api):
    done = stream_events(query(api, "What is a CAN error frame?", domain="automotive", stream=True))[-1]
    assert all("/" not in s["source"] for s in done["sources"])
    assert done["sources"][0]["page"] == 1


def test_stored_metadata_keeps_the_zero_based_page_and_path(api):
    stored = api.chroma.get_collection(config.COLLECTION_NAME).get(where={"domain": "automotive"})["metadatas"]
    assert min(m["page"] for m in stored) == 0
    assert all("/" in m["source"] for m in stored)
