import requests
from typing import List, Dict, Any
from src.vector_store import query_similar_chunks


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


def ask_question(collection, question: str, n_results: int = 3, filter_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Complete RAG pipeline: retrieve relevant chunks and generate answer.

    Args:
        collection: ChromaDB collection
        question: User's question
        n_results: Number of chunks to retrieve
        filter_metadata: Optional metadata filter (e.g., {"domain": "automotive"})

    Returns:
        Dictionary with answer, sources, and retrieved chunks
    """
    print(f"\nQuestion: {question}")
    print("="*60)

    # Step 1: Retrieve relevant chunks
    print("Step 1: Retrieving relevant chunks...")
    results = query_similar_chunks(collection, question, n_results=n_results, filter_metadata=filter_metadata)

    chunks = results['documents'][0]
    metadatas = results['metadatas'][0]

    print(f"✅ Retrieved {len(chunks)} chunks\n")

    # Step 2: Generate answer
    print("Step 2: Generating answer with LLM...")
    answer = generate_answer_ollama(question, chunks)
    print("✅ Answer generated\n")

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

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": chunks
    }
