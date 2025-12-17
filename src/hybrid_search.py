"""
Hybrid Search Module - Combining Semantic and Keyword Search

This module implements hybrid search using:
- Semantic search: Embedding-based similarity (ChromaDB)
- Keyword search: BM25 algorithm for exact term matching
- Fusion: Reciprocal Rank Fusion (RRF) to combine results

Usage:
    from src.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine(collection)
    results = engine.search(query, domain="automotive", n_results=5)
"""

from typing import List, Dict, Optional, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
import pickle
from pathlib import Path


class HybridSearchEngine:
    """
    Hybrid search engine combining semantic and keyword search.

    Attributes:
        collection: ChromaDB collection for semantic search
        bm25: BM25 index for keyword search
        all_documents: List of all documents
        all_metadatas: List of all document metadata
        all_ids: List of all document IDs
    """

    def __init__(self, collection, bm25_index_path: Optional[str] = None):
        """
        Initialize hybrid search engine.

        Args:
            collection: ChromaDB collection
            bm25_index_path: Path to saved BM25 index (optional)
        """
        self.collection = collection
        self.bm25 = None
        self.all_documents = None
        self.all_metadatas = None
        self.all_ids = None

        # Load or build BM25 index
        if bm25_index_path and Path(bm25_index_path).exists():
            print(f"Loading BM25 index from: {bm25_index_path}")
            self._load_bm25_index(bm25_index_path)
        else:
            print("Building BM25 index from ChromaDB...")
            self._build_bm25_index()

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization for BM25.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens (lowercase words)
        """
        return text.lower().split()

    def _build_bm25_index(self):
        """Build BM25 index from all documents in ChromaDB."""
        # Get all documents
        doc_count = self.collection.count()
        all_data = self.collection.get(
            limit=doc_count,
            include=["documents", "metadatas"]
        )

        self.all_documents = all_data['documents']
        self.all_metadatas = all_data['metadatas']
        self.all_ids = all_data['ids']

        # Tokenize and build BM25
        tokenized_docs = [self._tokenize(doc) for doc in self.all_documents]
        self.bm25 = BM25Okapi(tokenized_docs)

        print(f"✅ BM25 index built with {len(self.all_documents):,} documents")

    def _load_bm25_index(self, path: str):
        """Load pre-built BM25 index from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        self.bm25 = data['bm25']
        self.all_documents = data['documents']
        self.all_metadatas = data['metadatas']
        self.all_ids = data['ids']

        print(f"✅ BM25 index loaded: {len(self.all_documents):,} documents")

    def save_bm25_index(self, path: str):
        """
        Save BM25 index to file for faster loading.

        Args:
            path: Path to save index
        """
        with open(path, 'wb') as f:
            pickle.dump({
                'bm25': self.bm25,
                'documents': self.all_documents,
                'metadatas': self.all_metadatas,
                'ids': self.all_ids
            }, f)
        print(f"✅ BM25 index saved to: {path}")

    def semantic_search(
        self,
        query: str,
        n_results: int = 10,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        Semantic search using embeddings.

        Args:
            query: Search query
            n_results: Number of results to return
            domain: Optional domain filter

        Returns:
            List of search results with metadata
        """
        filter_metadata = {"domain": domain} if domain else None

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_metadata
        )

        return [
            {
                "id": results['ids'][0][i],
                "document": results['documents'][0][i],
                "distance": results['distances'][0][i],
                "metadata": results['metadatas'][0][i]
            }
            for i in range(len(results['ids'][0]))
        ]

    def bm25_search(
        self,
        query: str,
        n_results: int = 10,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        BM25 keyword search.

        Args:
            query: Search query
            n_results: Number of results to return
            domain: Optional domain filter

        Returns:
            List of search results with metadata
        """
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top N indices
        top_indices = np.argsort(scores)[::-1]

        # Filter by domain if specified
        results = []
        for idx in top_indices:
            if domain and self.all_metadatas[idx].get('domain') != domain:
                continue

            results.append({
                "id": self.all_ids[idx],
                "document": self.all_documents[idx],
                "score": scores[idx],
                "metadata": self.all_metadatas[idx]
            })

            if len(results) >= n_results:
                break

        return results

    def reciprocal_rank_fusion(
        self,
        semantic_results: List[Dict],
        bm25_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """
        Combine semantic and BM25 results using Reciprocal Rank Fusion.

        RRF Formula: RRF(d) = Σ 1 / (k + rank(d))
        where k=60 is a standard constant from literature.

        Args:
            semantic_results: Results from semantic search
            bm25_results: Results from BM25 search
            k: RRF constant (default: 60)

        Returns:
            Fused results sorted by RRF score
        """
        # Calculate RRF scores
        rrf_scores = {}

        # Add semantic results
        for rank, result in enumerate(semantic_results, 1):
            doc_id = result['id']
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Add BM25 results
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result['id']
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build result list
        fused_results = []
        for doc_id in sorted_ids:
            # Find document in either result set
            doc = None
            for result in semantic_results + bm25_results:
                if result['id'] == doc_id:
                    doc = result
                    break

            if doc:
                fused_results.append({
                    "id": doc_id,
                    "document": doc['document'],
                    "rrf_score": rrf_scores[doc_id],
                    "metadata": doc['metadata']
                })

        return fused_results

    def search(
        self,
        query: str,
        n_results: int = 5,
        domain: Optional[str] = None,
        method: str = "hybrid"
    ) -> List[Dict]:
        """
        Perform search using specified method.

        Args:
            query: Search query
            n_results: Number of final results to return
            domain: Optional domain filter
            method: Search method - "semantic", "bm25", or "hybrid" (default)

        Returns:
            List of search results with metadata
        """
        if method == "semantic":
            return self.semantic_search(query, n_results, domain)

        elif method == "bm25":
            return self.bm25_search(query, n_results, domain)

        elif method == "hybrid":
            # Get more results for fusion (typically 2-3x final count)
            retrieval_count = n_results * 3

            semantic_results = self.semantic_search(query, retrieval_count, domain)
            bm25_results = self.bm25_search(query, retrieval_count, domain)

            # Fuse and return top N
            fused_results = self.reciprocal_rank_fusion(semantic_results, bm25_results)
            return fused_results[:n_results]

        else:
            raise ValueError(f"Invalid method: {method}. Use 'semantic', 'bm25', or 'hybrid'")


def get_hybrid_results(
    collection,
    query: str,
    n_results: int = 3,
    domain: Optional[str] = None
) -> Tuple[List[str], List[Dict]]:
    """
    Convenience function for hybrid search (compatible with existing code).

    Args:
        collection: ChromaDB collection
        query: Search query
        n_results: Number of results
        domain: Optional domain filter

    Returns:
        Tuple of (documents, metadatas)
    """
    # Initialize engine (will cache BM25 index)
    if not hasattr(get_hybrid_results, '_engine'):
        get_hybrid_results._engine = HybridSearchEngine(collection)

    # Perform hybrid search
    results = get_hybrid_results._engine.search(
        query=query,
        n_results=n_results,
        domain=domain,
        method="hybrid"
    )

    # Extract documents and metadata
    documents = [r['document'] for r in results]
    metadatas = [r['metadata'] for r in results]

    return documents, metadatas
