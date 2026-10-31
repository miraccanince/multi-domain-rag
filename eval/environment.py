"""Record the conditions of an evaluation run, so results can be interpreted and repeated."""

import datetime
import importlib.metadata as metadata
import json
import platform
import subprocess
import urllib.request

from eval import fetch_data, sources
from rag import config, qa_chain
from rag.retrieval import reranker

PACKAGES = ["sentence-transformers", "torch", "chromadb", "rank-bm25", "pypdf", "pandas", "numpy", "langchain"]


def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=10,
                              cwd=sources.EVAL_DIR.parent).stdout.strip()
    except Exception:
        return "unknown"


def _ollama(path: str, payload: dict = None):
    try:
        request = urllib.request.Request(
            f"{config.OLLAMA_URL}{path}",
            data=json.dumps(payload).encode() if payload else None,
            headers={"content-type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except Exception as error:
        return {"error": str(error)}


def describe_environment() -> dict:
    model_info = _ollama("/api/show", {"model": config.LLM_MODEL})
    return {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_uncommitted_changes": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {name: metadata.version(name) for name in PACKAGES},
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "llm": {
            "name": config.LLM_MODEL,
            "ollama_version": _ollama("/api/version").get("version"),
            "details": model_info.get("details"),
            "parameters": model_info.get("parameters"),
        },
        "pipeline": {
            "pdf_chunk_size": 1000,
            "pdf_chunk_overlap": 200,
            "rrf_k": 60,
            "context_chunks": qa_chain.MAX_CONTEXT_CHUNKS,
            "context_chars_per_chunk": qa_chain.MAX_CHUNK_CHARS,
            "reranker_preview_chars": reranker.PREVIEW_CHARS,
            "reranker_temperature": 0.1,
            "reranker_candidates_per_final_result": 3,
        },
        "data": {
            "nist_sha256": sources.NIST_FILES,
            "epa_zip_sha256": sources.EPA_ZIP_SHA256,
            "epa_snapshot_sha256": fetch_data.sha256_of(sources.EPA_SNAPSHOT),
            "questions_sha256": fetch_data.sha256_of(sources.EVAL_DIR / "questions.jsonl"),
        },
    }
