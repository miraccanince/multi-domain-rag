"""
Unit tests for vector store operations.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from langchain.schema import Document
from src.vector_store import (
    initialize_chroma_db,
    index_documents,
    query_similar_chunks,
    get_collection_stats,
    get_available_domains
)


class TestVectorStore:
    """Test ChromaDB vector store operations."""

    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_documents(self):
        """Create sample documents for testing."""
        return [
            Document(
                page_content="Machine learning is a subset of AI.",
                metadata={"domain": "tech", "source": "test.pdf", "page": 1}
            ),
            Document(
                page_content="Deep learning uses neural networks.",
                metadata={"domain": "tech", "source": "test.pdf", "page": 2}
            ),
            Document(
                page_content="The weather is sunny today.",
                metadata={"domain": "weather", "source": "test2.pdf", "page": 1}
            )
        ]

    def test_initialize_chroma_db(self, temp_db_dir):
        """Test database initialization."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        assert client is not None
        assert collection is not None
        assert collection.count() == 0

    def test_index_documents(self, temp_db_dir, sample_documents):
        """Test document indexing."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        # Index documents
        count = index_documents(collection, sample_documents)

        assert count == 3
        assert collection.count() == 3

    def test_query_similar_chunks(self, temp_db_dir, sample_documents):
        """Test similarity search."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        # Index documents
        index_documents(collection, sample_documents)

        # Query
        results = query_similar_chunks(
            collection,
            query_text="What is machine learning?",
            n_results=2
        )

        assert 'documents' in results
        assert 'metadatas' in results
        assert len(results['documents'][0]) == 2

    def test_domain_filtering(self, temp_db_dir, sample_documents):
        """Test filtering by domain."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        index_documents(collection, sample_documents)

        # Query with domain filter
        results = query_similar_chunks(
            collection,
            query_text="AI and ML",
            n_results=5,
            filter_metadata={"domain": "tech"}
        )

        # Should only return tech domain documents
        assert all(m['domain'] == 'tech' for m in results['metadatas'][0])

    def test_get_collection_stats(self, temp_db_dir, sample_documents):
        """Test collection statistics."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        index_documents(collection, sample_documents)
        stats = get_collection_stats(collection)

        assert stats['total_documents'] == 3
        assert 'sample_metadata' in stats

    def test_get_available_domains(self, temp_db_dir, sample_documents):
        """Test domain extraction."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        index_documents(collection, sample_documents)
        domains = get_available_domains(collection)

        assert isinstance(domains, dict)
        assert 'tech' in domains
        assert 'weather' in domains
        assert domains['tech'] == 2
        assert domains['weather'] == 1

    def test_uuid_based_ids(self, temp_db_dir, sample_documents):
        """Test that document IDs are unique UUIDs."""
        client, collection = initialize_chroma_db(
            persist_directory=temp_db_dir,
            collection_name="test_collection"
        )

        # Index twice to ensure no collisions
        index_documents(collection, sample_documents)
        index_documents(collection, sample_documents)

        # Should have 6 documents (no updates)
        assert collection.count() == 6
