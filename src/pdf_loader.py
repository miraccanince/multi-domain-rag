from pathlib import Path
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document

def load_pdfs_from_directory(directory_path: str, chunk_size: int = 1000, chunk_overlap: int = 200, domain: str = None) -> List[Document]:
    """
    Load all PDFs from a directory and split into chunks.

    Args:
        directory_path: Path to directory containing PDFs
        chunk_size: Maximum characters per chunk (default: 1000)
        chunk_overlap: Overlap between chunks (default: 200)
        domain: Domain name to add to metadata (auto-detected from folder name if None)

    Returns:
        List of document chunks with metadata
    """
    # 1. Get all PDF files
    pdf_dir = Path(directory_path)
    pdf_files = list(pdf_dir.glob("*.pdf"))

    # Auto-detect domain from folder name
    if domain is None:
        domain = pdf_dir.name

    print(f"Found {len(pdf_files)} PDF files")

    # 2. Load and chunk each PDF
    all_chunks = []
    for pdf_path in pdf_files:
        print(f"\nLoading: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        chunks = text_splitter.split_documents(pages)

        # Add domain to metadata
        for chunk in chunks:
            chunk.metadata['domain'] = domain
            chunk.metadata['source_type'] = 'pdf'

        all_chunks.extend(chunks)
        print(f"  - {len(pages)} pages → {len(chunks)} chunks")

    # 3. Print total
    print(f"\nTotal chunks: {len(all_chunks)}")
    return all_chunks

