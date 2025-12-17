"""
Query Reranker Module - LLM-based relevance scoring

This module implements LLM-based reranking to improve retrieval quality:
- Takes initial retrieval results (e.g., top 10 chunks)
- Uses LLM to score relevance to the query
- Returns top-k most relevant chunks

Usage:
    from src.reranker import rerank_chunks

    chunks = ["chunk1", "chunk2", ...]
    metadatas = [{"source": "doc1.pdf"}, ...]

    top_chunks, top_metadatas = rerank_chunks(
        query="What is CAN protocol?",
        chunks=chunks,
        metadatas=metadatas,
        top_k=3
    )
"""

import requests
from typing import List, Dict, Tuple, Optional
import json
import re


def rerank_with_ollama(
    query: str,
    chunks: List[str],
    metadatas: List[Dict],
    top_k: int = 3,
    model: str = "llama3.2:3b"
) -> Tuple[List[str], List[Dict]]:
    """
    Rerank chunks using Ollama LLM for relevance scoring.

    Args:
        query: User's question
        chunks: List of document chunks to rerank
        metadatas: List of metadata dicts for each chunk
        top_k: Number of top chunks to return
        model: Ollama model name

    Returns:
        Tuple of (top_chunks, top_metadatas)
    """
    if len(chunks) == 0:
        return [], []

    if len(chunks) <= top_k:
        # No need to rerank if we have fewer chunks than requested
        return chunks, metadatas

    # Build prompt with all chunks
    chunks_text = ""
    for i, chunk in enumerate(chunks, 1):
        # Truncate long chunks for efficiency
        preview = chunk[:300] + "..." if len(chunk) > 300 else chunk
        chunks_text += f"\n[{i}] {preview}\n"

    prompt = f"""You are a relevance scoring expert. Your task is to rank documents by their relevance to a question.

Question: {query}

Documents:{chunks_text}

Analyze each document and rank them by relevance to the question. Return ONLY the top {top_k} document numbers in order of relevance (most relevant first).

Output format (numbers only, comma-separated):
Example: 3,7,1

Your ranking:"""

    # Call Ollama API
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent ranking
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"⚠️  Reranking failed: {response.status_code}, using original order")
            return chunks[:top_k], metadatas[:top_k]

        # Parse response
        result = response.json()["response"].strip()

        # Extract numbers from response
        # Look for pattern like "3,7,1" or "3, 7, 1" or "[3,7,1]"
        numbers = re.findall(r'\d+', result)

        if not numbers:
            print(f"⚠️  Could not parse reranking result: '{result}', using original order")
            return chunks[:top_k], metadatas[:top_k]

        # Convert to indices (1-based to 0-based)
        ranked_indices = []
        for num_str in numbers[:top_k]:  # Take only top_k
            idx = int(num_str) - 1  # Convert to 0-based
            if 0 <= idx < len(chunks):
                ranked_indices.append(idx)

        # If we don't have enough valid indices, fill with remaining
        if len(ranked_indices) < top_k:
            remaining = [i for i in range(len(chunks)) if i not in ranked_indices]
            ranked_indices.extend(remaining[:top_k - len(ranked_indices)])

        # Reorder chunks and metadatas
        reranked_chunks = [chunks[i] for i in ranked_indices]
        reranked_metadatas = [metadatas[i] for i in ranked_indices]

        return reranked_chunks, reranked_metadatas

    except Exception as e:
        print(f"⚠️  Reranking error: {e}, using original order")
        return chunks[:top_k], metadatas[:top_k]


def rerank_chunks(
    query: str,
    chunks: List[str],
    metadatas: List[Dict],
    top_k: int = 3,
    method: str = "ollama"
) -> Tuple[List[str], List[Dict]]:
    """
    Rerank chunks using specified method.

    Args:
        query: User's question
        chunks: List of document chunks to rerank
        metadatas: List of metadata dicts for each chunk
        top_k: Number of top chunks to return
        method: Reranking method - "ollama" (default) or "none"

    Returns:
        Tuple of (reranked_chunks, reranked_metadatas)
    """
    if method == "none":
        # No reranking, just return top_k
        return chunks[:top_k], metadatas[:top_k]

    elif method == "ollama":
        return rerank_with_ollama(query, chunks, metadatas, top_k)

    else:
        raise ValueError(f"Invalid reranking method: {method}. Use 'ollama' or 'none'")


def score_chunk_relevance(
    query: str,
    chunk: str,
    model: str = "llama3.2:3b"
) -> float:
    """
    Score a single chunk's relevance to the query (1-10 scale).

    Note: This is slower than batch reranking. Use rerank_with_ollama() instead
    for better performance.

    Args:
        query: User's question
        chunk: Document chunk to score
        model: Ollama model name

    Returns:
        Relevance score (1-10, higher is more relevant)
    """
    prompt = f"""Rate how relevant this document is to answering the question.
Scale: 1-10 (1=not relevant, 10=highly relevant)

Question: {query}

Document: {chunk[:500]}

Return ONLY a number between 1-10.
Score:"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                }
            },
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()["response"].strip()
            # Extract first number
            numbers = re.findall(r'\d+', result)
            if numbers:
                score = float(numbers[0])
                return min(max(score, 1), 10)  # Clamp to 1-10

    except Exception as e:
        print(f"⚠️  Scoring error for chunk: {e}")

    # Default score if error
    return 5.0
