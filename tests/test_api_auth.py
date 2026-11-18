"""
Endpoints that read or store user data reject requests without a token, and
CORS only allows the configured origin.
"""
import pytest
from fastapi.testclient import TestClient

import api.main as api_main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api_main.limiter, "enabled", False)
    return TestClient(api_main.app)


PROTECTED = [
    ("post", "/query", {"question": "What is OBD-II?"}),
    ("post", "/search", {"query": "OBD-II"}),
    ("post", "/feedback", {"question": "q", "answer": "a", "rating": 1}),
    ("get", "/feedback/stats", None),
    ("get", "/feedback/export", None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_protected_endpoint_requires_token(client, method, path, body):
    response = getattr(client, method)(path, **({"json": body} if body else {}))

    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/", "/health", "/domains"])
def test_public_endpoints_need_no_token(client, path):
    assert client.get(path).status_code != 401


def test_cors_allows_only_the_configured_origin(client):
    allowed = client.options("/health", headers={
        "Origin": "http://localhost:8501", "Access-Control-Request-Method": "GET"})
    blocked = client.options("/health", headers={
        "Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-origin" not in blocked.headers
