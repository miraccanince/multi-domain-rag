"""
CSV Loader for E-commerce Product Data
Loads fashion product data from CSV and converts each row to a Document.
"""

import pandas as pd
from pathlib import Path
from typing import List
from langchain.schema import Document


def load_csv_as_documents(csv_path: str, text_columns: List[str] = None, domain: str = None) -> List[Document]:
    """
    Load CSV file and convert each row to a LangChain Document.

    Args:
        csv_path: Path to CSV file
        text_columns: Columns to combine into document text.
                      If None, uses ['BrandName', 'Deatils', 'Sizes', 'Category']
        domain: Domain name to add to metadata (auto-detected from folder name if None)

    Returns:
        List of Document objects with product information
    """

    # Default columns for text content
    if text_columns is None:
        text_columns = ['BrandName', 'Deatils', 'Sizes', 'Category']

    # Auto-detect domain from folder name
    if domain is None:
        csv_file = Path(csv_path)
        domain = csv_file.parent.name

    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    # Drop rows with missing critical data
    df = df.dropna(subset=['BrandName', 'Deatils'])

    print(f"Found {len(df)} valid products")

    documents = []
    for idx, row in df.iterrows():
        # Create text content by combining specified columns
        text_parts = []
        for col in text_columns:
            if col in row and pd.notna(row[col]):
                text_parts.append(f"{col}: {row[col]}")

        # Add pricing information
        if pd.notna(row.get('MRP')):
            text_parts.append(f"Original Price: {row['MRP']}")
        if pd.notna(row.get('SellPrice')):
            text_parts.append(f"Selling Price: {row['SellPrice']}")
        if pd.notna(row.get('Discount')):
            text_parts.append(f"Discount: {row['Discount']}")

        text_content = "\n".join(text_parts)

        # Create metadata with all columns
        metadata = {
            'source': csv_path,
            'source_type': 'csv',
            'domain': domain,
            'row_id': str(idx),
            'brand': str(row.get('BrandName', '')),
            'category': str(row.get('Category', '')),
            'sell_price': str(row.get('SellPrice', '')),
            'mrp': str(row.get('MRP', '')),
            'discount': str(row.get('Discount', ''))
        }

        doc = Document(
            page_content=text_content,
            metadata=metadata
        )
        documents.append(doc)

    print(f"Created {len(documents)} documents from CSV")
    return documents


def load_all_csvs_from_directory(directory_path: str) -> List[Document]:
    """
    Load all CSV files from a directory.

    Args:
        directory_path: Path to directory containing CSV files

    Returns:
        List of all documents from all CSV files
    """
    csv_dir = Path(directory_path)
    csv_files = list(csv_dir.glob("*.csv"))

    print(f"Found {len(csv_files)} CSV files in {directory_path}")

    all_documents = []
    for csv_path in csv_files:
        docs = load_csv_as_documents(str(csv_path))
        all_documents.extend(docs)

    print(f"\nTotal documents from all CSVs: {len(all_documents)}")
    return all_documents
