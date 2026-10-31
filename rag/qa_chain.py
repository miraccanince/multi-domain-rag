import requests
import re
import time
import json
from typing import List, Dict, Any, Optional
from rag.retrieval.vector_store import query_similar_chunks
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.reranker import rerank_chunks
from rag.caching.cache_manager import get_query_cache, get_performance_monitor
from rag import config


# Answers that start with this prefix are error messages, not model output.
LLM_ERROR_PREFIX = "[LLM error] "


# Shown when retrieval finds nothing, so the LLM is not asked to answer from an empty context.
NO_ANSWER = "I don't have enough information in the indexed documents to answer this question."

MAX_CONTEXT_CHUNKS = 3
MAX_CHUNK_CHARS = 1000  # equal to the PDF chunk size, so a chunk is not cut off in the prompt


def build_prompt(question: str, context_chunks: List[str]) -> str:
    """Build the prompt used for answer generation (shared by the CLI and the API)."""
    context_parts = []
    for i, chunk in enumerate(context_chunks[:MAX_CONTEXT_CHUNKS], 1):
        context_parts.append(f"[Document {i}]\n{chunk[:MAX_CHUNK_CHARS]}")

    context = "\n\n".join(context_parts)

    return f"""You are a helpful assistant. Answer based ONLY on the context below.

Context:
{context}

Question: {question}

Instructions:
- Be concise (2-3 sentences max)
- Cite document numbers
- If not in context, say "I don't have enough information"

Answer:"""


def display_name(path: Any) -> str:
    """File name only, so responses do not reveal directories on the server."""
    return re.split(r"[\\/]", str(path))[-1] or "Unknown"


def display_page(page: Any) -> Any:
    """Pages are stored 0-based for indexing. People read them 1-based."""
    return page + 1 if isinstance(page, int) and not isinstance(page, bool) else page


def public_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """A copy of chunk metadata that is safe to show: file name only, 1-based page."""
    shown = dict(metadata)
    if 'source' in shown:
        shown['source'] = display_name(shown['source'])
    if 'page' in shown:
        shown['page'] = display_page(shown['page'])
    return shown


def format_sources(chunks: List[str], metadatas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Describe the retrieved chunks for the response (file, page or CSV row)."""
    sources = []
    for chunk, metadata in zip(chunks, metadatas):
        source_info = {
            "source": display_name(metadata.get('source', 'Unknown')),
            "source_type": metadata.get('source_type', 'pdf'),
            "chunk_preview": chunk[:200] + "..."
        }

        if metadata.get('source_type') == 'csv':
            source_info['row_id'] = metadata.get('row_id', 'N/A')
            source_info['brand'] = metadata.get('brand', 'N/A')
            source_info['category'] = metadata.get('category', 'N/A')
            source_info['price'] = metadata.get('sell_price', 'N/A')
        else:
            source_info['page'] = display_page(metadata.get('page', 'N/A'))

        sources.append(source_info)
    return sources


_REFUSAL = re.compile(r"don'?t have enough information", re.IGNORECASE)
_CITATION = re.compile(r"Documents?\s+((?:\d+|,|and|&|\s)+)", re.IGNORECASE)


def mark_cited(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Set source["cited"] to True for the documents the answer refers to.

    The prompt numbers the chunks "Document 1", "Document 2", ... and asks the model
    to cite them. Only the first MAX_CONTEXT_CHUNKS chunks are in the prompt, so
    later ones can never be cited. A refusal ("I don't have enough information")
    cites nothing, even if it mentions a document. A source that is not cited was
    retrieved but is not evidence for the answer.
    """
    cited = set()
    if not _REFUSAL.search(answer):
        for group in _CITATION.findall(answer):
            cited.update(int(n) for n in re.findall(r"\d+", group))
    for position, source in enumerate(sources, 1):
        source["cited"] = position <= MAX_CONTEXT_CHUNKS and position in cited
    return sources


def warm_up_model(model: str = config.LLM_MODEL, timeout: int = 60) -> bool:
    """
    Pre-load the model into memory to avoid timeout on first query.

    Args:
        model: Ollama model name
        timeout: Timeout for model loading (default: 60s)

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"Warming up model '{model}'...")
        print("   (This may take up to 60 seconds on first run)")

        response = requests.post(
            f"{config.OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": "Hello",
                "stream": False,
                "options": {
                    "num_predict": 1  # Just 1 token to load the model
                }
            },
            timeout=timeout
        )

        if response.status_code == 200:
            print(f"Model '{model}' loaded and ready!")
            return True
        else:
            print(f"Model warm-up returned status {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        print(f"Model warm-up timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"Model warm-up failed: {e}")
        return False


def generate_answer_ollama(question: str, context_chunks: List[str], model: str = config.LLM_MODEL, timeout: int = 120, stream: bool = True) -> str:
    """
    Generate answer using Ollama local LLM.

    Args:
        question: User's question
        context_chunks: Relevant document chunks
        model: Ollama model name
        timeout: Request timeout in seconds (default: 120)
        stream: Use streaming mode for faster response (default: True)

    Returns:
        Generated answer
    """
    prompt = build_prompt(question, context_chunks)

    try:
        if stream:
            # Streaming mode - model loading can take time on first request
            response = requests.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "num_predict": 150,  # Limit response length for speed
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                stream=True,
                timeout=30  # 30s for model loading + first token
            )

            if response.status_code != 200:
                return f"{LLM_ERROR_PREFIX}HTTP {response.status_code}"

            # Collect streamed response
            print("   ", end="", flush=True)
            full_response = ""

            # No timeout after streaming starts
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            token = data['response']
                            print(token, end="", flush=True)
                            full_response += token

                        # Check if done
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue

            print()  # New line after streaming
            return full_response.strip() if full_response else f"{LLM_ERROR_PREFIX}no response generated"

        else:
            # Non-streaming mode (fallback)
            response = requests.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"{LLM_ERROR_PREFIX}HTTP {response.status_code} - {response.text}"

    except requests.exceptions.Timeout:
        return f"{LLM_ERROR_PREFIX}the request to Ollama timed out. Check that Ollama is running: 'ollama serve'"

    except requests.exceptions.ConnectionError:
        return f"{LLM_ERROR_PREFIX}cannot connect to Ollama. Start it with 'ollama serve' and pull the model with 'ollama pull {model}'."

    except Exception as e:
        return f"{LLM_ERROR_PREFIX}{e}"


def ask_question(
    collection,
    question: str,
    n_results: int = 3,
    filter_metadata: Dict[str, Any] = None,
    search_method: str = "hybrid",
    use_reranking: bool = True,
    use_cache: bool = True,
    stream: bool = True,
    engine: Optional[HybridSearchEngine] = None
) -> Dict[str, Any]:
    """
    Complete RAG pipeline: retrieve relevant chunks and generate answer.

    Args:
        collection: ChromaDB collection
        question: User's question
        n_results: Number of chunks to retrieve (final count after reranking)
        filter_metadata: Optional metadata filter (e.g., {"domain": "automotive"})
        search_method: Search method - "semantic", "bm25", or "hybrid" (default)
        use_reranking: Whether to use LLM reranking (default: True)
        use_cache: Whether to use query result caching (default: True)
        stream: Whether to use streaming mode for LLM generation (default: True)
        engine: Hybrid search engine to use. Pass the caller's engine so that it
                reflects documents added or removed. If None, a module-level
                engine is built once and reused.

    Returns:
        Dictionary with answer, sources, and retrieved chunks
    """
    start_time = time.time()

    print(f"\nQuestion: {question}")
    print("="*60)

    # Get cache and monitor
    cache = get_query_cache()
    monitor = get_performance_monitor()

    # Try cache first
    domain = filter_metadata.get("domain") if filter_metadata else None
    cached_result = None
    if use_cache:
        cached_result = cache.get(question, domain=domain, method=search_method, n_results=n_results)
        if cached_result is not None:
            print("Cache hit! Returning cached result...")
            elapsed_time = time.time() - start_time
            monitor.record_query(total_time=elapsed_time)
            print(f"Total time: {elapsed_time:.3f}s\n")
            return cached_result

    # Step 1: Retrieve relevant chunks
    search_start = time.time()

    # If using reranking, retrieve more chunks initially (3x the final count)
    initial_n_results = n_results * 3 if use_reranking else n_results

    search_desc = f"{search_method} search"
    if use_reranking:
        search_desc += f" + reranking"
    else:
        search_desc += f" (no reranking)"

    print(f"Step 1: Retrieving relevant chunks ({search_desc})...")

    # Initialize hybrid search engine once
    if search_method in ["hybrid", "bm25"] and engine is None:
        if not hasattr(ask_question, '_hybrid_engine'):
            ask_question._hybrid_engine = HybridSearchEngine(collection)
        engine = ask_question._hybrid_engine

    # Try to retrieve chunks with smart fallback
    chunks = []
    metadatas = []

    # For small domains, start with fewer results
    if domain:
        # Try: initial -> n_results -> 1
        attempts = list(set([initial_n_results, n_results, 1]))  # Remove duplicates
        attempts.sort(reverse=True)
    else:
        attempts = [initial_n_results]  # All domains - should work fine

    for i, attempt_n in enumerate(attempts):
        try:
            if search_method in ["hybrid", "bm25"]:
                results = engine.search(
                    query=question,
                    n_results=attempt_n,
                    domain=domain,
                    method=search_method
                )
                chunks = [r['document'] for r in results]
                metadatas = [r['metadata'] for r in results]
            else:
                # Semantic search only
                results = query_similar_chunks(collection, question, n_results=attempt_n, filter_metadata=filter_metadata)
                chunks = results['documents'][0]
                metadatas = results['metadatas'][0]

            # Success!
            if i > 0:
                print(f"   Retrieved {len(chunks)} chunks with reduced count")
            break

        except Exception as e:
            error_str = str(e).lower()
            is_size_error = any(term in error_str for term in ['contigious', 'ef or m is too small', 'hnsw'])

            if is_size_error and i < len(attempts) - 1:
                next_attempt = attempts[i + 1]
                print(f"   Domain too small for {attempt_n} results, trying {next_attempt}...")
                continue
            elif i == len(attempts) - 1:
                # Last attempt failed
                raise Exception(f"Cannot retrieve documents from domain '{domain}'. Domain might be too small or empty. Error: {e}")
            else:
                # Different error - raise immediately
                raise

    search_time = time.time() - search_start

    if len(chunks) == 0:
        print("No results found, skipping generation")
        return {
            "question": question,
            "answer": NO_ANSWER,
            "sources": [],
            "retrieved_chunks": []
        }

    print(f"Retrieved {len(chunks)} chunks ({search_time:.3f}s)")

    # Step 1.5: Rerank if enabled
    rerank_time = 0.0
    if use_reranking and len(chunks) > n_results:
        rerank_start = time.time()
        print(f"   Reranking to top {n_results}...")
        chunks, metadatas = rerank_chunks(
            query=question,
            chunks=chunks,
            metadatas=metadatas,
            top_k=n_results,
            method="ollama"
        )
        rerank_time = time.time() - rerank_start
        print(f"   Reranking complete ({rerank_time:.3f}s)")

    print()

    # Step 2: Generate answer
    gen_start = time.time()
    print("Step 2: Generating answer with LLM...")
    answer = generate_answer_ollama(question, chunks, stream=stream)
    gen_time = time.time() - gen_start
    print(f"Answer generated ({gen_time:.3f}s)\n")

    # Step 3: Format response
    sources = mark_cited(answer, format_sources(chunks, metadatas))

    result = {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": chunks
    }

    # Cache result
    if use_cache:
        cache.set(question, result, domain=domain, method=search_method, n_results=n_results)

    # Record performance
    total_time = time.time() - start_time
    monitor.record_query(
        total_time=total_time,
        search_time=search_time,
        rerank_time=rerank_time,
        generation_time=gen_time
    )

    print(f"Total time: {total_time:.3f}s")

    return result
