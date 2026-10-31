"""
Tests for /query and the semantic cache, with Ollama, the embedding model
and the search engine replaced by fakes.
"""
import json

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from rag.caching.semantic_cache import SemanticCache

VECTORS = {
    "What is OBD-II?": [1.0, 0.8, 0.6, 0.4],
    "What does OBD-II mean?": [0.95, 0.82, 0.58, 0.42],
    "How do I bake bread?": [0.0, 1.0, 0.0, -1.0],
}


class FakeEngine:
    def search(self, query, n_results, domain=None, method="hybrid"):
        return [{"document": "OBD-II is a diagnostic standard.",
                 "metadata": {"source": "obd.pdf", "source_type": "pdf", "page": 1}}]


class FakeOllamaResponse:
    status_code = 200

    def __init__(self, tokens):
        self.tokens = tokens

    def iter_lines(self, decode_unicode=True):
        for token in self.tokens:
            yield json.dumps({"response": token, "done": False})
        yield json.dumps({"response": "", "done": True})


@pytest.fixture
def client(tmp_path, monkeypatch):
    cache = SemanticCache(cache_file=tmp_path / "cache.json")
    calls = {"ollama": 0, "tokens": ["OBD-II ", "is a diagnostic standard."]}

    def fake_post(*args, **kwargs):
        calls["ollama"] += 1
        return FakeOllamaResponse(calls["tokens"])

    monkeypatch.setattr(api_main, "get_semantic_cache", lambda: cache)
    monkeypatch.setattr(api_main, "create_embedding", lambda text: VECTORS[text])
    monkeypatch.setattr(api_main, "hybrid_engine", FakeEngine())
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr(api_main.limiter, "enabled", False)

    test_client = TestClient(api_main.app)
    test_client.cache = cache
    test_client.calls = calls
    return test_client


def ask(client, question, **overrides):
    body = {"question": question, "search_method": "bm25",
            "use_reranking": False, "stream": True}
    body.update(overrides)
    return client.post("/query", json=body)


def ndjson(response):
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_streaming_answer_is_cached(client):
    lines = ndjson(ask(client, "What is OBD-II?"))
    assert [m["type"] for m in lines][-1] == "done"
    assert client.calls["ollama"] == 1
    assert len(client.cache.cache) == 1
    entry = next(iter(client.cache.cache.values()))
    assert entry["answer"] == "OBD-II is a diagnostic standard."
    assert entry["sources"][0]["source"] == "obd.pdf"


def test_streaming_cache_hit_returns_ndjson(client):
    ask(client, "What is OBD-II?")
    response = ask(client, "What does OBD-II mean?")

    assert response.headers["content-type"].startswith("application/x-ndjson")
    lines = ndjson(response)
    assert [m["type"] for m in lines] == ["metadata", "token", "done"]
    assert lines[0]["cache_hit"] is True
    assert lines[0]["cache_similarity"] >= 0.85
    assert lines[1]["token"] == "OBD-II is a diagnostic standard."
    assert lines[2]["sources"][0]["source"] == "obd.pdf"
    assert lines[2]["total_time"] == 0.0
    assert client.calls["ollama"] == 1  # the second request did not reach the LLM


def test_unrelated_question_misses_cache(client):
    ask(client, "What is OBD-II?")
    lines = ndjson(ask(client, "How do I bake bread?"))
    assert not lines[0].get("cache_hit")
    assert client.calls["ollama"] == 2


def test_non_streaming_cache_hit_returns_json(client):
    ask(client, "What is OBD-II?")
    response = ask(client, "What does OBD-II mean?", stream=False)
    body = response.json()
    assert body["answer"] == "OBD-II is a diagnostic standard."
    assert body["metadata"]["cache_hit"] is True


def test_non_streaming_answer_is_cached(client, monkeypatch):
    monkeypatch.setattr(api_main, "ask_question", lambda **kw: {
        "question": kw["question"], "answer": "Cached by non-streaming.",
        "sources": [], "retrieved_chunks": ["c"]})
    ask(client, "What is OBD-II?", stream=False)
    assert len(client.cache.cache) == 1


def test_empty_answer_is_not_cached(client):
    client.calls["tokens"] = []
    ask(client, "What is OBD-II?")
    assert client.cache.cache == {}


def test_llm_error_text_is_not_cached(client, monkeypatch):
    monkeypatch.setattr(api_main, "ask_question", lambda **kw: {
        "question": kw["question"],
        "answer": api_main.LLM_ERROR_PREFIX + "cannot connect to Ollama",
        "sources": [], "retrieved_chunks": ["c"]})
    ask(client, "What is OBD-II?", stream=False)
    assert client.cache.cache == {}


def test_use_cache_false_skips_cache(client):
    ask(client, "What is OBD-II?", use_cache=False)
    assert client.cache.cache == {}


def test_refresh_after_document_change_clears_caches(client, monkeypatch):
    ask(client, "What is OBD-II?")
    assert client.cache.cache
    monkeypatch.setattr(api_main, "HybridSearchEngine", lambda col: FakeEngine())
    monkeypatch.setattr(api_main, "collection", object())
    api_main.refresh_search_state()
    assert client.cache.cache == {}


def test_user_listing_endpoint_is_removed(client):
    assert client.get("/auth/users").status_code in (404, 405)
