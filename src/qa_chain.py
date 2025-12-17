import requests
import time
from typing import List, Dict, Any, Optional
from src.vector_store import query_similar_chunks
from src.hybrid_search import HybridSearchEngine
from src.reranker import rerank_chunks
from src.cache_manager import get_query_cache, get_performance_monitor


def generate_answer_ollama(question: str, context_chunks: List[str], model: str = "llama3.2:3b") -> str:
    """
    Generate answer using Ollama local LLM.

    Args:
        question: User's question
        context_chunks: Relevant document chunks
        model: Ollama model name

    Returns:
        Generated answer
    """
    # Create prompt with context
    context = "\n\n".join([f"[Document {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)])

    prompt = f"""You are a helpful assistant answering questions about technical documentation and product catalogs.

Context from documents:
{context}

Question: {question}

Instructions:
- Answer based ONLY on the context provided above
- If the answer is not in the context, say "I don't have enough information to answer this question"
- Be concise and specific
- Cite which document number you're using (e.g., "According to Document 1...")

Answer:"""

    # Call Ollama API
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }
    )

    if response.status_code == 200:
        return response.json()["response"]
    else:
        return f"Error: {response.status_code} - {response.text}"


def ask_question(
    collection,
    question: str,
    n_results: int = 3,
    filter_metadata: Dict[str, Any] = None,
    search_method: str = "hybrid",
    use_reranking: bool = True,
    use_cache: bool = True
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
            print("⚡ Cache hit! Returning cached result...")
            elapsed_time = time.time() - start_time
            monitor.record_query(total_time=elapsed_time)
            print(f"⏱️  Total time: {elapsed_time:.3f}s\n")
            return cached_result

    # Step 1: Retrieve relevant chunks
    search_start = time.time()

    # If using reranking, retrieve more chunks initially (3x the final count)
    initial_n_results = n_results * 3 if use_reranking else n_results

    search_desc = f"{search_method} search"
    if use_reranking:
        search_desc += f" + reranking"

    print(f"Step 1: Retrieving relevant chunks ({search_desc})...")

    if search_method in ["hybrid", "bm25"]:
        # Use hybrid search engine (singleton)
        if not hasattr(ask_question, '_hybrid_engine'):
            ask_question._hybrid_engine = HybridSearchEngine(collection)

        results = ask_question._hybrid_engine.search(
            query=question,
            n_results=initial_n_results,
            domain=domain,
            method=search_method
        )

        chunks = [r['document'] for r in results]
        metadatas = [r['metadata'] for r in results]

    else:
        # Use semantic search only (original method)
        results = query_similar_chunks(collection, question, n_results=initial_n_results, filter_metadata=filter_metadata)
        chunks = results['documents'][0]
        metadatas = results['metadatas'][0]

    search_time = time.time() - search_start
    print(f"✅ Retrieved {len(chunks)} chunks ({search_time:.3f}s)")

    # Step 1.5: Rerank if enabled
    rerank_time = 0.0
    if use_reranking and len(chunks) > n_results:
        rerank_start = time.time()
        print(f"   🔄 Reranking to top {n_results}...")
        chunks, metadatas = rerank_chunks(
            query=question,
            chunks=chunks,
            metadatas=metadatas,
            top_k=n_results,
            method="ollama"
        )
        rerank_time = time.time() - rerank_start
        print(f"   ✅ Reranking complete ({rerank_time:.3f}s)")

    print()

    # Step 2: Generate answer
    gen_start = time.time()
    print("Step 2: Generating answer with LLM...")
    answer = generate_answer_ollama(question, chunks)
    gen_time = time.time() - gen_start
    print(f"✅ Answer generated ({gen_time:.3f}s)\n")

    # Step 3: Format response
    sources = []
    for i, metadata in enumerate(metadatas):
        source_info = {
            "source": metadata.get('source', 'Unknown'),
            "source_type": metadata.get('source_type', 'pdf'),
            "chunk_preview": chunks[i][:200] + "..."
        }

        # Add type-specific metadata
        if metadata.get('source_type') == 'csv':
            source_info['row_id'] = metadata.get('row_id', 'N/A')
            source_info['brand'] = metadata.get('brand', 'N/A')
            source_info['category'] = metadata.get('category', 'N/A')
            source_info['price'] = metadata.get('sell_price', 'N/A')
        else:  # PDF
            source_info['page'] = metadata.get('page', 'N/A')

        sources.append(source_info)

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

    print(f"⏱️  Total time: {total_time:.3f}s")

    return result
