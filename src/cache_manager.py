"""
Cache Manager - Performance optimization for RAG system

This module provides:
- Query result caching with TTL (Time-To-Live)
- LRU (Least Recently Used) eviction policy
- Memory-efficient storage
- Cache statistics and monitoring

Usage:
    from src.cache_manager import QueryCache

    cache = QueryCache(max_size=1000, ttl_seconds=3600)

    # Try to get from cache
    result = cache.get(query, domain)
    if result is None:
        # Compute result
        result = expensive_search(query)
        cache.set(query, domain, result)
"""

from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict
import time
import hashlib


class QueryCache:
    """
    LRU cache with TTL for query results.

    Features:
    - LRU eviction when max_size reached
    - TTL-based expiration
    - Cache hit/miss statistics
    - Memory-efficient key hashing
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cached items (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _make_key(self, query: str, domain: Optional[str] = None,
                  method: str = "hybrid", n_results: int = 3) -> str:
        """
        Create cache key from query parameters.

        Args:
            query: Search query
            domain: Optional domain filter
            method: Search method
            n_results: Number of results

        Returns:
            Hashed cache key
        """
        # Create unique key from parameters
        key_parts = [query.lower().strip(), str(domain), method, str(n_results)]
        key_string = "|".join(key_parts)

        # Hash for memory efficiency
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, query: str, domain: Optional[str] = None,
            method: str = "hybrid", n_results: int = 3) -> Optional[Any]:
        """
        Get cached result if available and not expired.

        Args:
            query: Search query
            domain: Optional domain filter
            method: Search method
            n_results: Number of results

        Returns:
            Cached result or None if not found/expired
        """
        key = self._make_key(query, domain, method, n_results)

        if key in self.cache:
            cached_data, timestamp = self.cache[key]

            # Check if expired
            if time.time() - timestamp < self.ttl_seconds:
                # Move to end (mark as recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return cached_data
            else:
                # Expired - remove
                del self.cache[key]

        self.misses += 1
        return None

    def set(self, query: str, result: Any, domain: Optional[str] = None,
            method: str = "hybrid", n_results: int = 3):
        """
        Store result in cache.

        Args:
            query: Search query
            result: Result to cache
            domain: Optional domain filter
            method: Search method
            n_results: Number of results
        """
        key = self._make_key(query, domain, method, n_results)

        # Remove oldest item if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self.cache.popitem(last=False)  # Remove oldest (FIFO)
            self.evictions += 1

        # Store with current timestamp
        self.cache[key] = (result, time.time())
        self.cache.move_to_end(key)  # Mark as most recent

    def clear(self):
        """Clear all cached items."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "ttl_seconds": self.ttl_seconds
        }

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self.cache)


class PerformanceMonitor:
    """
    Track and report performance metrics.

    Monitors:
    - Query response times
    - Cache hit rates
    - Component-level timings (search, rerank, generation)
    """

    def __init__(self):
        self.queries_count = 0
        self.total_time = 0.0
        self.search_time = 0.0
        self.rerank_time = 0.0
        self.generation_time = 0.0

    def record_query(self, total_time: float, search_time: float = 0.0,
                     rerank_time: float = 0.0, generation_time: float = 0.0):
        """
        Record timing for a query.

        Args:
            total_time: Total query time
            search_time: Search component time
            rerank_time: Reranking time
            generation_time: Answer generation time
        """
        self.queries_count += 1
        self.total_time += total_time
        self.search_time += search_time
        self.rerank_time += rerank_time
        self.generation_time += generation_time

    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Dictionary with timing stats
        """
        if self.queries_count == 0:
            return {
                "queries_count": 0,
                "avg_total_time": 0.0,
                "avg_search_time": 0.0,
                "avg_rerank_time": 0.0,
                "avg_generation_time": 0.0
            }

        return {
            "queries_count": self.queries_count,
            "avg_total_time": round(self.total_time / self.queries_count, 3),
            "avg_search_time": round(self.search_time / self.queries_count, 3),
            "avg_rerank_time": round(self.rerank_time / self.queries_count, 3),
            "avg_generation_time": round(self.generation_time / self.queries_count, 3)
        }

    def reset(self):
        """Reset all statistics."""
        self.queries_count = 0
        self.total_time = 0.0
        self.search_time = 0.0
        self.rerank_time = 0.0
        self.generation_time = 0.0


# Global instances
_query_cache = None
_performance_monitor = None


def get_query_cache(max_size: int = 1000, ttl_seconds: int = 3600) -> QueryCache:
    """
    Get global query cache instance (singleton).

    Args:
        max_size: Maximum cache size
        ttl_seconds: Cache TTL in seconds

    Returns:
        QueryCache instance
    """
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _query_cache


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get global performance monitor instance (singleton).

    Returns:
        PerformanceMonitor instance
    """
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
