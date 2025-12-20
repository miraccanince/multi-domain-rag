# FlexiRAG Test Suite

## Overview

Comprehensive unit tests for FlexiRAG core modules with **100% pass rate**.

## Test Coverage

### ✅ test_embeddings.py (5 tests)
Tests for embedding generation:
- Single embedding creation
- Batch embedding generation
- Empty string handling
- Embedding similarity validation
- Different batch size handling

### ✅ test_vector_store.py (7 tests)
Tests for ChromaDB vector store operations:
- Database initialization
- Document indexing
- Similarity search
- Domain filtering
- Collection statistics
- Available domains extraction
- UUID-based unique IDs

### ✅ test_cache_manager.py (8 tests)
Tests for query caching:
- Basic get/set operations
- Cache miss handling
- LRU eviction policy
- TTL expiration
- Cache clearing
- Statistics tracking
- Different cache sizes

### ✅ test_csv_loader.py (6 tests)
Tests for CSV document loading:
- Fashion domain CSV loading
- Generic CSV loading
- Auto text column detection
- Empty CSV handling
- NaN value handling
- Domain metadata

## Running Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

### Run specific test file:
```bash
pytest tests/test_embeddings.py -v
```

### Run specific test:
```bash
pytest tests/test_embeddings.py::TestEmbeddings::test_create_single_embedding -v
```

## Test Results

```
============================= test session starts ==============================
collected 26 items

tests/test_cache_manager.py::TestCacheManager::test_cache_set_and_get PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_miss PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_lru_eviction PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_ttl_expiration PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_clear PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_update_existing_key PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_stats PASSED
tests/test_cache_manager.py::TestCacheManager::test_cache_different_sizes PASSED
tests/test_csv_loader.py::TestCSVLoader::test_load_fashion_csv PASSED
tests/test_csv_loader.py::TestCSVLoader::test_load_generic_csv PASSED
tests/test_csv_loader.py::TestCSVLoader::test_auto_detect_text_columns PASSED
tests/test_csv_loader.py::TestCSVLoader::test_empty_csv PASSED
tests/test_csv_loader.py::TestCSVLoader::test_csv_with_nan_values PASSED
tests/test_csv_loader.py::TestCSVLoader::test_domain_metadata PASSED
tests/test_embeddings.py::TestEmbeddings::test_create_single_embedding PASSED
tests/test_embeddings.py::TestEmbeddings::test_create_embedding_empty_string PASSED
tests/test_embeddings.py::TestEmbeddings::test_create_embeddings_batch PASSED
tests/test_embeddings.py::TestEmbeddings::test_embedding_similarity PASSED
tests/test_embeddings.py::TestEmbeddings::test_batch_size_parameter PASSED
tests/test_vector_store.py::TestVectorStore::test_initialize_chroma_db PASSED
tests/test_vector_store.py::TestVectorStore::test_index_documents PASSED
tests/test_vector_store.py::TestVectorStore::test_query_similar_chunks PASSED
tests/test_vector_store.py::TestVectorStore::test_domain_filtering PASSED
tests/test_vector_store.py::TestVectorStore::test_get_collection_stats PASSED
tests/test_vector_store.py::TestVectorStore::test_get_available_domains PASSED
tests/test_vector_store.py::TestVectorStore::test_uuid_based_ids PASSED

======================= 26 passed in 7.36s =================================
```

## Coverage Report

| Module | Statements | Miss | Cover |
|--------|-----------|------|-------|
| src/embeddings.py | 27 | 4 | 85% |
| src/vector_store.py | 54 | 4 | 93% |
| src/cache_manager.py | 78 | 24 | 69% |
| src/csv_loader.py | 50 | 11 | 78% |

**Core modules coverage**: 81% average

## Test Structure

```
tests/
├── __init__.py           # Test package init
├── conftest.py          # Pytest configuration & fixtures
├── test_embeddings.py   # Embedding tests
├── test_vector_store.py # Vector store tests
├── test_cache_manager.py # Cache tests
├── test_csv_loader.py   # CSV loader tests
└── README.md           # This file
```

## Writing New Tests

### Example test structure:
```python
import pytest
from src.module import function


class TestModule:
    """Test suite for module."""

    @pytest.fixture
    def setup_data(self):
        """Fixture for test data."""
        return {"key": "value"}

    def test_function_behavior(self, setup_data):
        """Test function with fixture."""
        result = function(setup_data)
        assert result == expected_value
```

### Best practices:
1. **One assertion per test** when possible
2. **Use descriptive test names** (test_what_when_expected)
3. **Use fixtures** for common setup
4. **Mock external dependencies** (LLM calls, API calls)
5. **Test edge cases** (empty input, invalid data)

## CI/CD Integration

Add to GitHub Actions workflow:
```yaml
- name: Run tests
  run: |
    pytest tests/ -v --cov=src --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Future Tests

Planned test additions:
- [ ] API endpoint tests (integration)
- [ ] PDF loader tests
- [ ] Hybrid search tests
- [ ] QA chain tests
- [ ] Reranker tests
- [ ] End-to-end tests
