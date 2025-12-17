#!/usr/bin/env python3
"""
RAG Documentation Assistant - Interactive Demo
Run this script to ask questions about your documentation across multiple domains.

FRAMEWORK DESIGN:
- Automatically detects all indexed domains
- Dynamic domain selection menu
- Zero code change needed when adding new domains
- Smart indexing: checks for new documents before starting
"""

import subprocess
from pathlib import Path
from src.vector_store import initialize_chroma_db, get_available_domains
from src.qa_chain import ask_question


def count_data_files() -> dict:
    """
    Count all files in data/ directory by domain.

    Returns:
        Dictionary with {domain_name: file_count}
    """
    data_path = Path("data")
    if not data_path.exists():
        return {}

    file_counts = {}
    for domain_folder in data_path.iterdir():
        if domain_folder.is_dir() and not domain_folder.name.startswith('.'):
            pdf_count = len(list(domain_folder.glob("*.pdf")))
            csv_count = len(list(domain_folder.glob("*.csv")))
            total = pdf_count + csv_count

            if total > 0:
                file_counts[domain_folder.name] = total

    return file_counts


def check_indexing_needed(collection) -> bool:
    """
    Check if indexing is needed by comparing DB count with data folder files.

    Returns:
        True if re-indexing might be needed, False otherwise
    """
    try:
        # Get current DB count
        db_count = collection.count()

        # Get data folder file counts
        data_files = count_data_files()

        if not data_files:
            return False

        # Get indexed domains
        try:
            indexed_domains = get_available_domains(collection)
        except:
            indexed_domains = {}

        # Check if there are new domains in data folder
        data_domain_names = set(data_files.keys())
        indexed_domain_names = set(indexed_domains.keys())

        new_domains = data_domain_names - indexed_domain_names

        if new_domains:
            print(f"\n⚠️  New domain(s) detected: {', '.join(new_domains)}")
            return True

        # If no documents indexed but data exists
        if db_count == 0 and data_files:
            print("\n⚠️  Database is empty but documents exist in data/")
            return True

        return False

    except Exception as e:
        print(f"\n⚠️  Could not check indexing status: {e}")
        return False


def run_indexing():
    """
    Run the indexing script.
    """
    print("\n" + "="*60)
    print("🔄 Running indexing process...")
    print("="*60)

    try:
        result = subprocess.run(
            ["./venv/bin/python3", "index_documents.py", "--yes"],
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print("\n✅ Indexing complete!")
            return True
        else:
            print(f"\n❌ Indexing failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n❌ Error running indexing: {e}")
        return False


def select_domain(domains: dict) -> str:
    """
    Interactive domain selection menu.

    Args:
        domains: Dictionary of {domain_name: document_count}

    Returns:
        Selected domain name or 'all' for no filtering
    """
    print("\n" + "="*60)
    print("📂 Select your domain:")
    print("="*60)

    domain_list = list(domains.keys())

    for i, (domain_name, count) in enumerate(domains.items(), 1):
        emoji = "🚗" if domain_name == "automotive" else "👗" if domain_name == "fashion" else "📁"
        print(f"{i}. {emoji} {domain_name.capitalize()} ({count:,} documents)")

    print(f"{len(domain_list) + 1}. 🔀 All domains (search everything)")

    while True:
        try:
            choice = input(f"\nYour choice (1-{len(domain_list) + 1}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(domain_list):
                selected = domain_list[choice_num - 1]
                print(f"\n✅ Domain: {selected.capitalize()}")
                return selected
            elif choice_num == len(domain_list) + 1:
                print("\n✅ Domain: All (searching across all domains)")
                return 'all'
            else:
                print(f"❌ Please enter a number between 1 and {len(domain_list) + 1}")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Invalid input. Please enter a number.")
        except EOFError:
            return None


def main():
    print("="*60)
    print("🤖 RAG Documentation Assistant")
    print("="*60)
    print("\nInitializing system...")

    # Load existing ChromaDB collection
    try:
        client, collection = initialize_chroma_db(
            persist_directory="./chroma_db",
            collection_name="documents"
        )

        doc_count = collection.count()

        # Check if indexing is needed
        if check_indexing_needed(collection):
            print("\n📊 Current database: {} documents".format(doc_count if doc_count > 0 else "0 (empty)"))

            try:
                response = input("\n🔄 Would you like to run indexing now? (yes/no): ").strip().lower()
                if response in ['yes', 'y', 'evet']:
                    if run_indexing():
                        # Reload collection after indexing
                        client, collection = initialize_chroma_db(
                            persist_directory="./chroma_db",
                            collection_name="documents"
                        )
                        doc_count = collection.count()
                    else:
                        print("\n⚠️  Continuing with existing database...")
                else:
                    print("\n⚠️  Skipping indexing. Using existing database...")
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️  Skipping indexing. Using existing database...")

        if doc_count == 0:
            print("\n❌ No documents found in database!")
            print("Please run: python3 index_documents.py")
            return

        # Discover available domains
        print("\n🔍 Discovering domains...")
        domains = get_available_domains(collection)

        if not domains:
            print("\n⚠️  No domain metadata found!")
            print("Re-index with: python3 index_documents.py --yes")
            return

        print(f"\n✅ System ready! {doc_count:,} documents loaded")

    except Exception as e:
        print(f"\n❌ Error loading database: {e}")
        print("Please make sure you have indexed documents first.")
        return

    # Domain selection
    selected_domain = select_domain(domains)

    if selected_domain is None:
        print("\n👋 Goodbye!")
        return

    # Interactive question loop
    print("\n" + "="*60)
    print("💬 Ask your questions!")
    print("="*60)
    print("\n🔍 Using: Hybrid Search (Semantic + BM25)")
    print("\nCommands:")
    print("  /switch  - Change domain")
    print("  /stats   - Show statistics")
    print("  /help    - Show this help")
    print("  /quit    - Exit\n")

    while True:
        print("-"*60)
        question = input("\n💬 Your question: ").strip()

        # Handle commands
        if question.lower() in ['/quit', '/exit', 'quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break

        elif question.lower() == '/switch':
            selected_domain = select_domain(domains)
            if selected_domain is None:
                break
            continue

        elif question.lower() == '/stats':
            print("\n📊 System Statistics:")
            print("="*60)
            print(f"Total documents: {doc_count:,}")
            print("\nDocuments by domain:")
            for domain_name, count in domains.items():
                print(f"  - {domain_name}: {count:,}")
            print(f"\nCurrent domain: {selected_domain}")
            print(f"Search method: Hybrid (Semantic + BM25)")
            continue

        elif question.lower() == '/help':
            print("\n💡 Help:")
            print("="*60)
            print("Commands:")
            print("  /switch  - Change domain")
            print("  /stats   - Show statistics")
            print("  /help    - Show this help")
            print("  /quit    - Exit")
            print("\nTips:")
            print("  - Ask specific questions for better results")
            print("  - Use domain filtering to avoid irrelevant results")
            print("  - Check sources to verify answer accuracy")
            print("\nSearch:")
            print("  - Using Hybrid search (Semantic + BM25 keyword)")
            print("  - Best for technical terms and conceptual queries")
            continue

        # Skip empty questions
        if not question:
            continue

        try:
            # Build metadata filter
            filter_metadata = None if selected_domain == 'all' else {"domain": selected_domain}

            # Get answer using RAG pipeline
            result = ask_question(collection, question, n_results=3, filter_metadata=filter_metadata)

            # Display answer
            print(f"\n🤖 Answer:")
            print("-"*60)
            print(result['answer'])

            # Display sources
            print(f"\n📚 Sources:")
            print("-"*60)
            for i, source in enumerate(result['sources'], 1):
                if source.get('source_type') == 'csv':
                    # CSV product
                    print(f"{i}. {source['source']} (Row {source['row_id']})")
                    print(f"   Brand: {source['brand']} | Category: {source['category']} | Price: {source['price']}")
                else:
                    # PDF document
                    print(f"{i}. {source['source']} (Page {source['page']})")
                print(f"   Preview: {source['chunk_preview'][:150]}...")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try asking another question.")


if __name__ == "__main__":
    main()
