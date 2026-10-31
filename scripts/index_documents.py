#!/usr/bin/env python3
"""
Index documents into ChromaDB
Run this once to load your documents (PDFs + CSVs) into the vector database.

FRAMEWORK DESIGN:
- Automatically detects domains from data/ folder structure
- Each subfolder in data/ = one domain
- Supports any number of domains
- Zero code change needed when adding new domains
"""

import argparse
from pathlib import Path
from rag.ingestion.pdf_loader import load_pdfs_from_directory
from rag.ingestion.csv_loader import load_all_csvs_from_directory
from rag import config
from rag.retrieval.vector_store import initialize_chroma_db, index_documents


def discover_domains(data_dir=config.DATA_DIR) -> dict:
    """
    Auto-discover domains from data directory structure.

    Returns:
        Dictionary with domain info: {domain_name: {'pdfs': count, 'csvs': count, 'path': path}}
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        return {}

    domains = {}
    for domain_folder in data_path.iterdir():
        if domain_folder.is_dir() and not domain_folder.name.startswith('.'):
            pdf_count = len(list(domain_folder.glob("*.pdf")))
            csv_count = len(list(domain_folder.glob("*.csv")))

            if pdf_count > 0 or csv_count > 0:
                domains[domain_folder.name] = {
                    'pdfs': pdf_count,
                    'csvs': csv_count,
                    'path': str(domain_folder)
                }

    return domains


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Index documents into ChromaDB')
    parser.add_argument('--domain', type=str, help='Index only specific domain')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm overwrite without prompting')
    args = parser.parse_args()

    print("="*60)
    print("Dynamic Multi-Domain Document Indexer")
    print("="*60)

    # Discover all domains
    print("\nDiscovering domains in data/ folder...")
    domains = discover_domains()

    if not domains:
        print("\nNo domains found!")
        print("Please create folders in data/ and add documents:")
        print("  data/automotive/  -> Add PDF files")
        print("  data/fashion/     -> Add CSV files")
        print("  data/medical/     -> Add any documents")
        return

    # Show discovered domains
    print(f"\nFound {len(domains)} domain(s):")
    for domain_name, info in domains.items():
        print(f"  {domain_name}: {info['pdfs']} PDFs, {info['csvs']} CSVs")

    # Filter by specific domain if requested
    if args.domain:
        if args.domain not in domains:
            print(f"\nDomain '{args.domain}' not found!")
            return
        domains = {args.domain: domains[args.domain]}
        print(f"\nIndexing only domain: {args.domain}")

    # Load documents from all domains
    all_documents = []
    domain_stats = {}

    for domain_name, info in domains.items():
        print(f"\nLoading domain: {domain_name}")
        domain_docs = []

        # Load PDFs
        if info['pdfs'] > 0:
            try:
                pdf_chunks = load_pdfs_from_directory(info['path'], domain=domain_name)
                domain_docs.extend(pdf_chunks)
            except Exception as e:
                print(f"Warning: Could not load PDFs: {e}")

        # Load CSVs
        if info['csvs'] > 0:
            try:
                csv_docs = load_all_csvs_from_directory(info['path'], domain=domain_name)
                domain_docs.extend(csv_docs)
            except Exception as e:
                print(f"Warning: Could not load CSVs: {e}")

        all_documents.extend(domain_docs)
        domain_stats[domain_name] = len(domain_docs)
        print(f"{domain_name}: {len(domain_docs)} documents loaded")

    if len(all_documents) == 0:
        print("\nNo documents loaded!")
        return

    print(f"\nTotal documents to index: {len(all_documents)}")

    # Step 3: Initialize ChromaDB
    print("\nStep 3: Initializing ChromaDB...")
    client, collection = initialize_chroma_db(
        persist_directory=config.CHROMA_DIR,
        collection_name=config.COLLECTION_NAME
    )

    # Check if already indexed
    existing_count = collection.count()
    if existing_count > 0:
        if args.yes:
            print(f"\nCollection already has {existing_count} documents. Overwriting (--yes flag)...")
        else:
            try:
                response = input(f"\nCollection already has {existing_count} documents. Overwrite? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Indexing cancelled.")
                    return
            except EOFError:
                print("\nCannot prompt in non-interactive mode. Use --yes flag to auto-confirm.")
                return
        # Delete and recreate collection
        client.delete_collection(name=config.COLLECTION_NAME)
        collection = client.create_collection(name=config.COLLECTION_NAME)
        print("Collection cleared.")

    # Step 4: Index documents
    print("\nStep 4: Creating embeddings and indexing...")
    index_documents(collection, all_documents, batch_size=32)

    # Step 5: Verify
    print("\nStep 5: Verification...")
    final_count = collection.count()
    print(f"Successfully indexed {final_count} documents!")

    # Show breakdown by domain
    print("\nDocuments by domain:")
    for domain_name, count in domain_stats.items():
        print(f"  - {domain_name}: {count} documents")

    print("\n" + "="*60)
    print("Indexing complete! You can now start the API (uvicorn api.main:app) or run: python -m scripts.chat_cli")
    print("="*60)
    print("\nTip: Add new domains by creating folders in data/")
    print("   Example: data/medical/ -> automatically detected on next run")


if __name__ == "__main__":
    main()
