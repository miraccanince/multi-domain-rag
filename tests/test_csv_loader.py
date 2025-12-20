"""
Unit tests for CSV loader.
"""
import pytest
import pandas as pd
import tempfile
from pathlib import Path
from src.csv_loader import load_csv_as_documents


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
