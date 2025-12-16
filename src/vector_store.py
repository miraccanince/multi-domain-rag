from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from src.embeddings import create_embedding, create_embeddings_batch


def initialize_chroma_db(persist_directory: str = "./chroma_db", collection_name: str = "documents"):
    """
    Initialize ChromaDB client and get or create a collection.

    Args:
        persist_directory: Directory to persist the database
        collection_name: Name of the collection to use

    Returns:
        Tuple of (client, collection)
    """
    print(f"Initializing ChromaDB at: {persist_directory}")

    # Create persistent client
    client = chromadb.PersistentClient(path=persist_directory)

    # Get or create collection
    try:
        collection = client.get_collection(name=collection_name)
        print(f"✅ Loaded existing collection: {collection_name}")
        print(f"   Documents in collection: {collection.count()}")
    except:
        collection = client.create_collection(name=collection_name)
        print(f"✅ Created new collection: {collection_name}")

    return client, collection


def index_documents(collection, chunks: List[Any], batch_size: int = 32):
    """
    Add documents with their embeddings to ChromaDB.

    Args:
        collection: ChromaDB collection
        chunks: List of LangChain Document objects with page_content and metadata
        batch_size: Number of documents to embed at once

    Returns:
        Number of documents indexed
    """
    print(f"\nIndexing {len(chunks)} documents...")

    # Extract texts and metadata
    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]

    # Create unique IDs
    ids = [f"chunk_{i}" for i in range(len(chunks))]

    # Create embeddings in batches
    print("Creating embeddings...")
    embeddings = create_embeddings_batch(texts, batch_size=batch_size)
    print(f"✅ Created {len(embeddings)} embeddings")

    # Add to ChromaDB in batches
    print("Adding to ChromaDB...")
    total_added = 0

    for i in range(0, len(chunks), batch_size):
        end_idx = min(i + batch_size, len(chunks))

        collection.add(
            embeddings=embeddings[i:end_idx],
            documents=texts[i:end_idx],
            metadatas=metadatas[i:end_idx],
            ids=ids[i:end_idx]
        )

        total_added += (end_idx - i)
        print(f"  Progress: {total_added}/{len(chunks)} documents indexed", end='\r')

    print(f"\n✅ Successfully indexed {total_added} documents")
    return total_added


def query_similar_chunks(
    collection,
    query_text: str,
    n_results: int = 5,
    filter_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Find similar chunks for a query text.

    Args:
        collection: ChromaDB collection
        query_text: Query string
        n_results: Number of similar chunks to return
        filter_metadata: Optional metadata filter (e.g., {"source": "CAN.pdf"})

    Returns:
        Dictionary with 'documents', 'metadatas', 'distances', and 'ids'
    """
    # Create query embedding
    query_embedding = create_embedding(query_text)

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=filter_metadata  # Optional filtering
    )

    return results


def get_collection_stats(collection) -> Dict[str, Any]:
    """
    Get statistics about a collection.

    Args:
        collection: ChromaDB collection

    Returns:
        Dictionary with collection statistics
    """
    count = collection.count()

    # Try to peek at some documents
    if count > 0:
        peek = collection.peek(limit=1)
        sample_metadata = peek['metadatas'][0] if peek['metadatas'] else {}
    else:
        sample_metadata = {}

    return {
        "total_documents": count,
        "sample_metadata": sample_metadata
    }


def get_available_domains(collection) -> Dict[str, int]:
    """
    Get all unique domains from the collection with document counts.

    Args:
        collection: ChromaDB collection

    Returns:
        Dictionary mapping domain names to document counts
        Example: {'automotive': 635, 'fashion': 30758}
    """
    total_count = collection.count()

    if total_count == 0:
        return {}

    # Get all documents (just metadata, not full content)
    # Note: ChromaDB doesn't have a direct "get unique values" method,
    # so we peek at all metadata and extract domains
    all_data = collection.get(limit=total_count, include=["metadatas"])

    domain_counts = {}
    for metadata in all_data['metadatas']:
        domain = metadata.get('domain', 'unknown')
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return domain_counts
