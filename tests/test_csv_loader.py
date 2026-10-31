"""
Unit tests for CSV loader.
"""
import pytest
import pandas as pd
import tempfile
from pathlib import Path
from rag.ingestion.csv_loader import load_csv_as_documents, load_all_csvs_from_directory


class TestCSVLoader:
    """Test CSV document loading."""

    @pytest.fixture
    def fashion_csv_file(self):
        """Create temporary fashion CSV file."""
        data = {
            'BrandName': ['Nike', 'Adidas', 'Puma'],
            'Deatils': ['Running shoes', 'Training shoes', 'Casual shoes'],
            'Sizes': ['7,8,9', '8,9,10', '7,8,9,10'],
            'Category': ['Sports', 'Sports', 'Casual'],
            'MRP': [100, 120, 80],
            'SellPrice': [80, 100, 70],
            'Discount': ['20%', '17%', '12%']
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            yield f.name

        # Cleanup
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def generic_csv_file(self):
        """Create temporary generic CSV file."""
        data = {
            'id': [1, 2, 3],
            'name': ['Product A', 'Product B', 'Product C'],
            'description': ['Desc A', 'Desc B', 'Desc C'],
            'price': [10.5, 20.0, 15.75]
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            yield f.name

        Path(f.name).unlink(missing_ok=True)

    def test_load_fashion_csv(self, fashion_csv_file):
        """Test loading fashion domain CSV."""
        documents = load_csv_as_documents(fashion_csv_file, domain='fashion')

        assert len(documents) == 3
        assert all(hasattr(doc, 'page_content') for doc in documents)
        assert all(hasattr(doc, 'metadata') for doc in documents)

        # Check metadata
        assert documents[0].metadata['domain'] == 'fashion'
        assert documents[0].metadata['source_type'] == 'csv'
        assert 'brand' in documents[0].metadata

    def test_load_generic_csv(self, generic_csv_file):
        """Test loading generic CSV."""
        documents = load_csv_as_documents(generic_csv_file, domain='products')

        assert len(documents) == 3

        # Check auto-detected text columns
        assert 'Product A' in documents[0].page_content or 'Desc A' in documents[0].page_content

        # Check metadata
        assert documents[0].metadata['domain'] == 'products'

    def test_auto_detect_text_columns(self, generic_csv_file):
        """Test automatic text column detection."""
        documents = load_csv_as_documents(generic_csv_file, domain='test')

        # Should exclude 'id' and numeric 'price'
        for doc in documents:
            assert 'name' in doc.page_content.lower() or 'desc' in doc.page_content.lower()

    def test_empty_csv(self):
        """Test loading empty CSV."""
        data = pd.DataFrame({'col1': [], 'col2': []})

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            data.to_csv(f.name, index=False)

            documents = load_csv_as_documents(f.name, domain='test')
            assert len(documents) == 0

            Path(f.name).unlink(missing_ok=True)

    def test_csv_with_nan_values(self):
        """Test CSV with NaN values."""
        data = {
            'name': ['Product A', None, 'Product C'],
            'description': ['Desc A', 'Desc B', None]
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)

            documents = load_csv_as_documents(f.name, domain='test')

            # Should keep rows with at least one valid value
            assert len(documents) > 0

            Path(f.name).unlink(missing_ok=True)

    def test_domain_metadata(self, generic_csv_file):
        """Test domain is correctly set in metadata."""
        documents = load_csv_as_documents(generic_csv_file, domain='custom_domain')

        assert all(doc.metadata['domain'] == 'custom_domain' for doc in documents)


class TestCSVDomainMetadata:
    """Domain metadata must reach the vector store and work as a filter."""

    def _write_domain(self, root, name, rows):
        folder = root / name
        folder.mkdir()
        pd.DataFrame(rows).to_csv(folder / "items.csv", index=False)
        return folder

    def test_directory_loader_uses_explicit_domain(self, tmp_path):
        folder = self._write_domain(tmp_path, "shop", {"name": ["a", "b"]})
        docs = load_all_csvs_from_directory(str(folder), domain="catalog")
        assert {d.metadata["domain"] for d in docs} == {"catalog"}

    def test_directory_loader_defaults_to_folder_name(self, tmp_path):
        folder = self._write_domain(tmp_path, "shop", {"name": ["a", "b"]})
        docs = load_all_csvs_from_directory(str(folder))
        assert {d.metadata["domain"] for d in docs} == {"shop"}

    def test_domain_is_never_none(self, tmp_path):
        folder = self._write_domain(tmp_path, "shop", {"name": ["a"]})
        docs = load_csv_as_documents(str(folder / "items.csv"))
        assert all(d.metadata["domain"] == "shop" for d in docs)

    def test_domain_filter_in_chroma(self, tmp_path, fake_embeddings):
        from rag.retrieval.vector_store import (
            initialize_chroma_db, index_documents, query_similar_chunks,
            get_available_domains)
        shop = self._write_domain(
            tmp_path, "shop", {"name": ["red dress", "blue jacket"]})
        cars = self._write_domain(
            tmp_path, "cars", {"name": ["engine torque", "brake pads"]})
        docs = (load_all_csvs_from_directory(str(shop), domain="shop")
                + load_all_csvs_from_directory(str(cars), domain="cars"))

        _, collection = initialize_chroma_db(str(tmp_path / "chroma"))
        index_documents(collection, docs)

        assert get_available_domains(collection) == {"shop": 2, "cars": 2}
        hits = query_similar_chunks(
            collection, "red dress", n_results=4,
            filter_metadata={"domain": "cars"})
        assert len(hits["documents"][0]) == 2
        assert all(m["domain"] == "cars" for m in hits["metadatas"][0])
