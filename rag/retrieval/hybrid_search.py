"""
Hybrid Search Module - Combining Semantic and Keyword Search

This module implements hybrid search using:
- Semantic search: Embedding-based similarity (ChromaDB)
- Keyword search: BM25 algorithm for exact term matching
- Fusion: Reciprocal Rank Fusion (RRF) to combine results

Usage:
    from rag.retrieval.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine(collection)
    results = engine.search(query, domain="automotive", n_results=5)
"""

from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi
import re

import numpy as np

from rag.retrieval.vector_store import query_similar_chunks


# Common English words that say nothing about the topic. Without this list, a question
# such as "What is the capital of France?" matches any document containing "is" or "the".
# Words that can carry meaning in technical text ("can" as in CAN bus, "not", "no",
# "must", "shall") are deliberately kept.
STOP_WORDS = frozenset("""
a an and are as at be been being by do does did for from had has have how i if in into is it
its of on or so than that the their them then there these they this those to was we were what
when where which who whom why will with you your
""".split())


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

    def __init__(self, collection):
        """
        Build the BM25 index from the current contents of the collection.

        The index lives in memory only. Create a new engine after documents
        are added or removed so that keyword search sees the change.

        Args:
            collection: ChromaDB collection
        """
        self.collection = collection
        self.bm25 = None
        self.all_documents = []
        self.all_metadatas = []
        self.all_ids = []
        self._build_bm25_index()
        self.size = len(self.all_ids)

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenization for BM25: lowercase words and numbers, punctuation removed,
        common English words dropped. Used for both documents and queries.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        return [t for t in re.findall(r"\w+", text.lower()) if t not in STOP_WORDS]

    def _build_bm25_index(self):
        """Build BM25 index from all documents in ChromaDB."""
        # Get all documents
        doc_count = self.collection.count()
        if doc_count == 0:
            return
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

        print(f"BM25 index built with {len(self.all_documents):,} documents")

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

        # Embed the query with the same sentence-transformers model that embedded
        # the documents. Passing query_texts would make ChromaDB use its own
        # default embedding function instead.
        results = query_similar_chunks(
            self.collection, query, n_results=n_results, filter_metadata=filter_metadata
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
        if self.bm25 is None:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []
        scores = self.bm25.get_scores(tokenized_query)
        query_terms = set(tokenized_query)

        # Get top N indices
        top_indices = np.argsort(scores)[::-1]

        # Filter by domain if specified
        results = []
        for idx in top_indices:
            if domain and self.all_metadatas[idx].get('domain') != domain:
                continue

            # A document that shares no term with the query is not a keyword match
            if query_terms.isdisjoint(self.bm25.doc_freqs[idx]):
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

        RRF Formula: RRF(d) = sum of 1 / (k + rank(d))
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
