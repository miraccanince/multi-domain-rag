"""
Unit tests for cache manager.
"""
import pytest
import time
from src.cache_manager import QueryCache


class TestCacheManager:
    """Test query caching functionality."""

    @pytest.fixture
    def cache(self):
        """Create fresh cache instance."""
        return QueryCache(max_size=3, ttl_seconds=2)

    def test_cache_set_and_get(self, cache):
        """Test basic cache operations."""
        cache.set("query1", "result1")

        assert cache.get("query1") == "result1"
        assert len(cache) == 1

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent_query")
        assert result is None

    def test_cache_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        cache.set("query1", "result1")
        cache.set("query2", "result2")
        cache.set("query3", "result3")

        # Cache is full (max_size=3)
        assert len(cache) == 3

        # Add one more - should evict query1 (least recently used)
        cache.set("query4", "result4")

        assert len(cache) == 3
        assert cache.get("query1") is None  # Evicted
        assert cache.get("query4") == "result4"  # New entry

    def test_cache_ttl_expiration(self, cache):
        """Test TTL-based expiration."""
        cache.set("query1", "result1")

        # Should exist initially
        assert cache.get("query1") == "result1"

        # Wait for TTL to expire (ttl_seconds=2)
        time.sleep(2.1)

        # Should be expired
        assert cache.get("query1") is None

    def test_cache_clear(self, cache):
        """Test cache clearing."""
        cache.set("query1", "result1")
        cache.set("query2", "result2")

        assert len(cache) == 2

        cache.clear()

        assert len(cache) == 0
        assert cache.get("query1") is None

    def test_cache_update_existing_key(self, cache):
        """Test updating existing cache key."""
        cache.set("query1", "result1")
        cache.set("query1", "result2")

        assert cache.get("query1") == "result2"
        assert len(cache) == 1  # Size shouldn't increase

    def test_cache_stats(self, cache):
        """Test cache statistics."""
        cache.set("query1", "result1")

        # Hit
        cache.get("query1")

        # Miss
        cache.get("query2")

        stats = cache.get_stats()

        assert stats['size'] == 1
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate_percent'] == 50.0

    def test_cache_different_sizes(self):
        """Test cache with different max sizes."""
        small_cache = QueryCache(max_size=1)

        small_cache.set("query1", "result1")
        small_cache.set("query2", "result2")

        # Should only keep 1 item
        assert len(small_cache) == 1
        assert small_cache.get("query1") is None
        assert small_cache.get("query2") == "result2"
