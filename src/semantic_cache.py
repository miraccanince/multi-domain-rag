"""
Semantic Cache Module

Embedding-based intelligent cache that can find similar queries
and return cached responses even for slightly different wordings.

Uses cosine similarity between query embeddings to determine cache hits.
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import threading


class SemanticCache:
    """
    Embedding-based cache for RAG queries.

    Stores query embeddings and finds similar queries using cosine similarity.
    More intelligent than string-based cache - can match semantically similar queries.
    """

    def __init__(
        self,
        cache_file: str = "semantic_cache.json",
        similarity_threshold: float = 0.85,
        max_cache_size: int = 1000
    ):
        """
        Initialize semantic cache.

        Args:
            cache_file: Path to cache storage file
            similarity_threshold: Minimum cosine similarity for cache hit (0-1)
            max_cache_size: Maximum number of cached entries
        """
        self.cache_file = Path(__file__).parent.parent / cache_file
        self.similarity_threshold = similarity_threshold
        self.max_cache_size = max_cache_size

        # In-memory cache: {cache_id: cache_entry}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        # Load existing cache
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Convert embedding lists back to numpy arrays
                    for cache_id, entry in data.items():
                        entry['query_embedding'] = np.array(entry['query_embedding'])
                        self.cache[cache_id] = entry
                print(f"Loaded {len(self.cache)} entries from semantic cache")
            except Exception as e:
                print(f"Warning: Could not load semantic cache: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Convert numpy arrays to lists for JSON serialization
            serializable_cache = {}
            for cache_id, entry in self.cache.items():
                serializable_entry = entry.copy()
                # Handle both numpy arrays and lists
                embedding = entry['query_embedding']
                if isinstance(embedding, np.ndarray):
                    serializable_entry['query_embedding'] = embedding.tolist()
                else:
                    serializable_entry['query_embedding'] = embedding
                serializable_cache[cache_id] = serializable_entry

            with open(self.cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save semantic cache: {e}")

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Returns:
            Similarity score between 0 and 1
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _find_similar_query(
        self,
        query_embedding: np.ndarray,
        domain: Optional[str] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Find most similar cached query.

        Args:
            query_embedding: Embedding of the query
            domain: Optional domain filter

        Returns:
            Tuple of (cache_id, similarity_score) if found, None otherwise
        """
        best_match = None
        best_similarity = 0.0

        for cache_id, entry in self.cache.items():
            # Filter by domain if specified
            if domain and entry.get('domain') != domain:
                continue

            # Calculate similarity
            similarity = self._cosine_similarity(
                query_embedding,
                entry['query_embedding']
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cache_id

        # Return only if above threshold
        if best_similarity >= self.similarity_threshold:
            return (best_match, best_similarity)
        return None

    def get(
        self,
        query: str,
        query_embedding,  # Can be list or np.ndarray
        domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Try to get cached result for query.

        Args:
            query: Query text (for logging)
            query_embedding: Embedding of the query (list or numpy array)
            domain: Optional domain filter

        Returns:
            Cached result if similar query found, None otherwise
        """
        with self.lock:
            # Convert to numpy array if list
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)

            result = self._find_similar_query(query_embedding, domain)

            if result:
                cache_id, similarity = result
                cached_entry = self.cache[cache_id]

                # Update hit count and last accessed time
                cached_entry['hit_count'] = cached_entry.get('hit_count', 0) + 1
                cached_entry['last_accessed'] = datetime.now().isoformat()

                print(f"Semantic cache HIT (similarity: {similarity:.3f})")
                print(f"  Original: {cached_entry['query_text']}")
                print(f"  New:      {query}")

                return {
                    'answer': cached_entry['answer'],
                    'sources': cached_entry['sources'],
                    'metadata': {
                        **cached_entry.get('metadata', {}),
                        'cache_hit': True,
                        'cache_similarity': similarity,
                        'cached_query': cached_entry['query_text']
                    }
                }

            return None

    def set(
        self,
        query: str,
        query_embedding,  # Can be list or np.ndarray
        answer: str,
        sources: List[Dict[str, Any]],
        domain: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store query result in cache.

        Args:
            query: Query text
            query_embedding: Embedding of the query (list or numpy array)
            answer: Generated answer
            sources: Retrieved sources
            domain: Optional domain
            metadata: Optional additional metadata
        """
        with self.lock:
            # Enforce max cache size (LRU-style eviction)
            if len(self.cache) >= self.max_cache_size:
                self._evict_oldest()

            # Generate cache ID
            cache_id = f"sc_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            # Convert embedding to numpy array if it's a list
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)

            # Store cache entry
            self.cache[cache_id] = {
                'cache_id': cache_id,
                'query_text': query,
                'query_embedding': query_embedding,
                'answer': answer,
                'sources': sources,
                'domain': domain,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'hit_count': 0
            }

            # Persist to disk
            self._save_cache()

    def _evict_oldest(self):
        """Evict least recently used cache entry."""
        if not self.cache:
            return

        # Find entry with oldest last_accessed time
        oldest_id = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].get('last_accessed', '0')
        )

        print(f"Evicting old cache entry: {self.cache[oldest_id]['query_text'][:50]}")
        del self.cache[oldest_id]

    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache = {}
            self._save_cache()
            print("Semantic cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.cache:
            return {
                'total_entries': 0,
                'total_hits': 0,
                'domains': {}
            }

        total_hits = sum(entry.get('hit_count', 0) for entry in self.cache.values())

        # Domain breakdown
        domains = {}
        for entry in self.cache.values():
            domain = entry.get('domain', 'unknown')
            if domain not in domains:
                domains[domain] = {'count': 0, 'hits': 0}
            domains[domain]['count'] += 1
            domains[domain]['hits'] += entry.get('hit_count', 0)

        return {
            'total_entries': len(self.cache),
            'total_hits': total_hits,
            'similarity_threshold': self.similarity_threshold,
            'max_size': self.max_cache_size,
            'domains': domains
        }


# Singleton instance
_semantic_cache: Optional[SemanticCache] = None
_cache_lock = threading.Lock()


def get_semantic_cache() -> SemanticCache:
    """Get or create the global semantic cache instance."""
    global _semantic_cache

    if _semantic_cache is None:
        with _cache_lock:
            if _semantic_cache is None:
                _semantic_cache = SemanticCache(
                    similarity_threshold=0.85,
                    max_cache_size=1000
                )

    return _semantic_cache
