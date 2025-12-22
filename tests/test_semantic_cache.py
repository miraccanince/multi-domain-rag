"""
Tests for semantic cache module.

Tests the embedding-based intelligent caching system that detects
semantically similar queries using cosine similarity.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path

from src.semantic_cache import SemanticCache


class TestSemanticCache:
    """Test suite for SemanticCache class."""

    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

    @pytest.fixture
    def cache(self, temp_cache_file):
        """Create a SemanticCache instance for testing."""
        return SemanticCache(
            cache_file=temp_cache_file,
            similarity_threshold=0.85,
            max_cache_size=10
        )

    def test_basic_cache_set_and_get(self, cache):
        """Test basic cache set and get with exact match."""
        query = "What is CAN protocol?"
        embedding = np.random.rand(384)
        answer = "CAN is a vehicle bus standard"
        sources = [{"text": "CAN protocol doc"}]

        # Set cache
        cache.set(query, embedding, answer, sources, domain="automotive")

        # Get with same embedding (exact match)
        result = cache.get(query, embedding, domain="automotive")

        assert result is not None
        assert result['answer'] == answer
        assert result['sources'] == sources
        assert result['metadata']['cache_hit'] is True
        assert abs(result['metadata']['cache_similarity'] - 1.0) < 0.001

    def test_cache_miss_on_different_query(self, cache):
        """Test cache miss when query embeddings are too different."""
        query1 = "What is CAN protocol?"
        embedding1 = np.array([1.0, 0.0, 0.0, 0.0])

        query2 = "What is the weather today?"
        embedding2 = np.array([0.0, 1.0, 0.0, 0.0])  # Orthogonal = 0 similarity

        # Set cache with first query
        cache.set(query1, embedding1, "CAN answer", [])

        # Try to get with very different query
        result = cache.get(query2, embedding2)

        assert result is None  # Should miss

    def test_semantic_similarity_matching(self, cache):
        """Test that semantically similar queries hit cache."""
        # Create two similar embeddings (high cosine similarity)
        embedding1 = np.array([1.0, 0.8, 0.6, 0.4])
        embedding2 = np.array([0.95, 0.82, 0.58, 0.42])  # Very similar

        query1 = "What is OBD-II?"
        query2 = "What does OBD-II mean?"

        # Set cache with first query
        cache.set(query1, embedding1, "OBD-II is a diagnostic system", [])

        # Get with similar embedding (paraphrased question)
        result = cache.get(query2, embedding2)

        assert result is not None
        assert result['answer'] == "OBD-II is a diagnostic system"
        assert result['metadata']['cache_similarity'] > 0.85

    def test_similarity_threshold(self, cache):
        """Test that queries below threshold don't hit cache."""
        # Create embeddings with similarity just below threshold
        embedding1 = np.array([1.0, 0.0, 0.0, 0.0])
        embedding2 = np.array([0.8, 0.6, 0.0, 0.0])  # ~0.8 similarity, below 0.85

        cache.set("Query 1", embedding1, "Answer 1", [])
        result = cache.get("Query 2", embedding2)

        # Should miss because similarity < 0.85
        assert result is None

    def test_domain_filtering(self, cache):
        """Test that cache respects domain filtering."""
        embedding = np.random.rand(384)

        # Set in automotive domain
        cache.set(
            "CAN question",
            embedding,
            "CAN answer",
            [],
            domain="automotive"
        )

        # Try to get with wrong domain
        result = cache.get("CAN question", embedding, domain="fashion")
        assert result is None  # Should miss - wrong domain

        # Get with correct domain
        result = cache.get("CAN question", embedding, domain="automotive")
        assert result is not None

    def test_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        # Fill cache to max size (10)
        for i in range(10):
            cache.set(
                f"query_{i}",
                np.random.rand(384),
                f"answer_{i}",
                []
            )

        assert len(cache.cache) == 10

        # Add one more - should evict oldest
        cache.set(
            "query_new",
            np.random.rand(384),
            "answer_new",
            []
        )

        assert len(cache.cache) == 10  # Still at max size

    def test_hit_count_tracking(self, cache):
        """Test that hit counts are tracked correctly."""
        embedding = np.random.rand(384)
        cache.set("test query", embedding, "test answer", [])

        # Get multiple times
        cache.get("test query", embedding)
        cache.get("test query", embedding)
        cache.get("test query", embedding)

        # Check hit count in cache entry
        cache_entry = list(cache.cache.values())[0]
        assert cache_entry['hit_count'] == 3

    def test_list_vs_numpy_array(self, cache):
        """Test that both list and numpy array embeddings work."""
        # Test with numpy array
        embedding_np = np.random.rand(384)
        cache.set("query1", embedding_np, "answer1", [])

        # Test with list
        embedding_list = embedding_np.tolist()
        result = cache.get("query1", embedding_list)

        assert result is not None
        assert result['answer'] == "answer1"

    def test_cache_persistence(self, temp_cache_file):
        """Test that cache persists to disk and loads correctly."""
        # Create cache and add entry
        cache1 = SemanticCache(cache_file=temp_cache_file)
        embedding = np.array([1.0, 2.0, 3.0, 4.0])
        cache1.set("test query", embedding, "test answer", [{"source": "doc1"}])

        # Create new cache instance (should load from disk)
        cache2 = SemanticCache(cache_file=temp_cache_file)

        # Should find the entry
        result = cache2.get("test query", embedding)
        assert result is not None
        assert result['answer'] == "test answer"

    def test_clear_cache(self, cache):
        """Test clearing all cache entries."""
        # Add some entries
        for i in range(5):
            cache.set(f"query_{i}", np.random.rand(384), f"answer_{i}", [])

        assert len(cache.cache) > 0

        # Clear cache
        cache.clear()

        assert len(cache.cache) == 0

    def test_cache_stats(self, cache):
        """Test cache statistics retrieval."""
        # Add entries with hits
        embedding1 = np.random.rand(384)
        embedding2 = np.random.rand(384)

        cache.set("query1", embedding1, "answer1", [], domain="automotive")
        cache.set("query2", embedding2, "answer2", [], domain="fashion")

        # Generate some hits
        cache.get("query1", embedding1, domain="automotive")
        cache.get("query1", embedding1, domain="automotive")

        stats = cache.get_stats()

        assert stats['total_entries'] == 2
        assert stats['total_hits'] == 2
        assert stats['similarity_threshold'] == 0.85
        assert stats['max_size'] == 10
        assert 'automotive' in stats['domains']
        assert 'fashion' in stats['domains']

    def test_empty_cache_stats(self, cache):
        """Test stats on empty cache."""
        stats = cache.get_stats()

        assert stats['total_entries'] == 0
        assert stats['total_hits'] == 0
        assert stats['domains'] == {}

    def test_cosine_similarity_calculation(self, cache):
        """Test cosine similarity calculation."""
        # Identical vectors = 1.0
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([1.0, 2.0, 3.0])
        similarity = cache._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001

        # Orthogonal vectors = 0.0
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        similarity = cache._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001

        # Opposite vectors = -1.0
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([-1.0, 0.0, 0.0])
        similarity = cache._cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.001

    def test_zero_vector_similarity(self, cache):
        """Test that zero vectors return 0 similarity."""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 2.0, 3.0])

        similarity = cache._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_metadata_storage(self, cache):
        """Test that custom metadata is stored and retrieved."""
        embedding = np.random.rand(384)
        custom_metadata = {"custom_field": "custom_value", "number": 42}

        cache.set(
            "test query",
            embedding,
            "test answer",
            [],
            metadata=custom_metadata
        )

        result = cache.get("test query", embedding)
        assert result['metadata']['custom_field'] == "custom_value"
        assert result['metadata']['number'] == 42

    def test_last_accessed_update(self, cache):
        """Test that last_accessed timestamp is updated on cache hits."""
        embedding = np.random.rand(384)
        cache.set("test query", embedding, "test answer", [])

        # Get cache entry ID
        cache_id = list(cache.cache.keys())[0]
        initial_accessed = cache.cache[cache_id]['last_accessed']

        # Small delay and access again
        import time
        time.sleep(0.01)
        cache.get("test query", embedding)

        updated_accessed = cache.cache[cache_id]['last_accessed']
        assert updated_accessed > initial_accessed

    def test_cached_query_in_metadata(self, cache):
        """Test that original cached query is returned in metadata."""
        embedding1 = np.array([1.0, 0.8, 0.6, 0.4])
        embedding2 = np.array([0.95, 0.82, 0.58, 0.42])

        original_query = "What is OBD-II?"
        paraphrased_query = "What does OBD-II mean?"

        cache.set(original_query, embedding1, "OBD answer", [])
        result = cache.get(paraphrased_query, embedding2)

        assert result is not None
        assert result['metadata']['cached_query'] == original_query

    def test_sources_preservation(self, cache):
        """Test that sources are preserved correctly."""
        embedding = np.random.rand(384)
        sources = [
            {"text": "Source 1", "page": 1},
            {"text": "Source 2", "page": 2}
        ]

        cache.set("test query", embedding, "test answer", sources)
        result = cache.get("test query", embedding)

        assert result['sources'] == sources
        assert len(result['sources']) == 2
        assert result['sources'][0]['page'] == 1
