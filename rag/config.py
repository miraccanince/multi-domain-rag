"""Paths and settings shared by the API, the scripts and the library code.

Everything can be overridden with environment variables. Runtime state
(vector store, users, caches, feedback) lives in STORAGE_DIR,
user documents live in DATA_DIR.
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("RAG_DATA_DIR", ROOT_DIR / "data"))
STORAGE_DIR = Path(os.getenv("RAG_STORAGE_DIR", ROOT_DIR / "storage"))

CHROMA_DIR = STORAGE_DIR / "chroma"
USERS_FILE = STORAGE_DIR / "users.json"
SEMANTIC_CACHE_FILE = STORAGE_DIR / "semantic_cache.json"
FEEDBACK_FILE = STORAGE_DIR / "feedback.json"
JWT_SECRET_FILE = STORAGE_DIR / "jwt_secret"

COLLECTION_NAME = "documents"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
