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
import requests
from pathlib import Path
from src.vector_store import initialize_chroma_db, get_available_domains
from src.qa_chain import ask_question, warm_up_model
from src.cache_manager import get_query_cache, get_performance_monitor


def check_ollama_running() -> bool:
    """
    Check if Ollama is running and accessible.

    Returns:
        True if Ollama is running, False otherwise
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        return response.status_code == 200
    except:
        return False


def check_and_clean_hanging_processes() -> bool:
    """
    Check for hanging Python processes connected to Ollama and clean them.

    Returns:
        True if cleanup was performed, False otherwise
    """
    try:
        # Check for hanging Python processes on Ollama port
        result = subprocess.run(
            ["lsof", "-i", ":11434"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return False

        # Parse output for Python processes
        lines = result.stdout.strip().split('\n')
        python_pids = []

        for line in lines[1:]:  # Skip header
            if 'Python' in line or 'python' in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    # Don't kill current process
                    if pid != str(subprocess.os.getpid()):
                        python_pids.append(pid)

        if not python_pids:
            return False

        # Found hanging processes
        print(f"\n⚠️  Found {len(python_pids)} hanging Python process(es) connected to Ollama")
        print("   These may be causing slowdowns or timeouts.")

        try:
            response = input("\n🧹 Clean them up? (yes/no): ").strip().lower()
            if response in ['yes', 'y', 'evet']:
                for pid in python_pids:
                    try:
                        subprocess.run(["kill", "-9", pid], check=False)
                    except:
                        pass
                print(f"✅ Cleaned up {len(python_pids)} hanging process(es)")

                # Restart Ollama for clean state
                print("\n🔄 Restarting Ollama for clean state...")
                subprocess.run(["pkill", "-9", "ollama"], check=False)
                subprocess.run(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                import time
                time.sleep(2)  # Wait for Ollama to start
                print("✅ Ollama restarted")
                return True
            else:
                print("⚠️  Skipped cleanup. System may be slow.")
                return False
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️  Skipped cleanup.")
            return False

    except Exception:
        # Silently fail - this is just a diagnostic feature
        return False


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

    # Check if Ollama is running
    print("🔍 Checking Ollama service...")
    if not check_ollama_running():
        print("⚠️  WARNING: Ollama is not running or not accessible!")
        print("   The system will work but LLM features (reranking and answer generation) will fail.")
        print("   To start Ollama: 'ollama serve' in another terminal")
        print("   To check if Ollama is running: 'ollama list'\n")
        try:
            response = input("Continue anyway? (yes/no): ").strip().lower()
            if response not in ['yes', 'y', 'evet']:
                print("\n👋 Please start Ollama and try again.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Exiting...")
            return
    else:
        print("✅ Ollama is running")

        # Check for and clean hanging processes
        check_and_clean_hanging_processes()

        # Warm up the model to avoid timeout on first query
        warm_up_model(model="llama3.2:3b", timeout=60)

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
    use_reranking = False  # Default: OFF for better performance
    skip_llm = False  # NOW USING STREAMING - no more timeouts!

    print("\n" + "="*60)
    print("💬 Ask your questions!")
    print("="*60)
    print("\n🔍 Configuration:")
    print("   Search: Hybrid (Semantic + BM25) + Caching")
    rerank_status = "ON ✅" if use_reranking else "OFF ⚡"
    llm_status = "SKIP (sources only)" if skip_llm else "ON ✅ (streaming mode)"
    print(f"   Reranking: {rerank_status}")
    print(f"   LLM Generation: {llm_status}")
    print("\n💡 Tip: Using STREAMING mode - answers appear instantly! Use /llm to toggle.")
    print("\nCommands:")
    print("  /switch   - Change domain")
    print("  /llm      - Toggle LLM answer generation")
    print("  /rerank   - Toggle reranking")
    print("  /stats    - Show statistics")
    print("  /cache    - Show cache statistics")
    print("  /perf     - Show performance metrics")
    print("  /help     - Show this help")
    print("  /quit     - Exit\n")

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

        elif question.lower() == '/llm':
            skip_llm = not skip_llm
            print("\n🔄 LLM answer generation toggled!")
            if skip_llm:
                print("   ⚡ LLM: SKIPPED")
                print("   • Shows retrieved document chunks only")
                print("   • No AI-generated answer")
                print("   • Very fast (~1-2s per query)")
                print("   • Read the sources directly")
            else:
                print("   ✅ LLM: ENABLED")
                print("   • Generates AI answer from sources")
                print("   • Requires working Ollama")
                print("   • Slower (~30-120s per query)")
            continue

        elif question.lower() == '/rerank':
            use_reranking = not use_reranking
            print("\n🔄 Reranking toggled!")
            if use_reranking:
                print("   ✅ Reranking: ON")
                print("   • More accurate relevance scoring")
                print("   • Uses LLM to select best results")
                print("   • Slower (~20s extra per query)")
            else:
                print("   ⚡ Reranking: OFF")
                print("   • Faster responses (~2-5s per query)")
                print("   • Uses hybrid search ranking only")
                print("   • Recommended for quick queries")
            continue

        elif question.lower() == '/stats':
            print("\n📊 System Statistics:")
            print("="*60)
            print(f"Total documents: {doc_count:,}")
            print("\nDocuments by domain:")
            for domain_name, count in domains.items():
                print(f"  - {domain_name}: {count:,}")
            print(f"\nCurrent domain: {selected_domain}")
            print(f"Search method: Hybrid (Semantic + BM25) + Caching")
            continue

        elif question.lower() == '/cache':
            cache = get_query_cache()
            stats = cache.get_stats()
            print("\n⚡ Cache Statistics:")
            print("="*60)
            print(f"Cache size: {stats['size']}/{stats['max_size']} items")
            print(f"Cache hits: {stats['hits']}")
            print(f"Cache misses: {stats['misses']}")
            print(f"Hit rate: {stats['hit_rate_percent']}%")
            print(f"Evictions: {stats['evictions']}")
            print(f"TTL: {stats['ttl_seconds']}s ({stats['ttl_seconds']//60} minutes)")
            print(f"Total requests: {stats['total_requests']}")
            continue

        elif question.lower() == '/perf':
            monitor = get_performance_monitor()
            stats = monitor.get_stats()
            print("\n⏱️  Performance Metrics:")
            print("="*60)
            print(f"Queries processed: {stats['queries_count']}")
            if stats['queries_count'] > 0:
                print(f"\nAverage times:")
                print(f"  Total: {stats['avg_total_time']:.3f}s")
                print(f"  Search: {stats['avg_search_time']:.3f}s")
                print(f"  Reranking: {stats['avg_rerank_time']:.3f}s")
                print(f"  Generation: {stats['avg_generation_time']:.3f}s")
            else:
                print("\nNo queries processed yet.")
            continue

        elif question.lower() == '/help':
            print("\n💡 Help:")
            print("="*60)
            print("Commands:")
            print("  /switch   - Change domain")
            print("  /llm      - Toggle LLM answer generation (default: OFF)")
            print("  /rerank   - Toggle reranking (default: OFF)")
            print("  /stats    - Show statistics")
            print("  /cache    - Show cache statistics")
            print("  /perf     - Show performance metrics")
            print("  /help     - Show this help")
            print("  /quit     - Exit")
            print("\nTips:")
            print("  - LLM is OFF by default - you'll see source documents directly")
            print("  - Use /llm to enable AI-generated answers (requires Ollama)")
            print("  - Ask specific questions for better results")
            print("  - Use domain filtering to avoid irrelevant results")
            print("  - Repeated queries are cached for faster responses")
            print("\nSearch:")
            print("  - Using Hybrid search (Semantic + BM25 keyword)")
            print("  - Query result caching with 1-hour TTL")
            print("  - Fast mode: Shows source documents (~1-2s)")
            print("  - LLM mode: Generates AI answers (~30-120s)")
            continue

        # Skip empty questions
        if not question:
            continue

        try:
            # Build metadata filter
            filter_metadata = None if selected_domain == 'all' else {"domain": selected_domain}

            if skip_llm:
                # Fast mode: Just search and show chunks, no LLM generation
                import time
                from src.hybrid_search import HybridSearchEngine

                print(f"\n⚡ Searching (no LLM generation)...")
                start = time.time()

                # Initialize search engine
                if not hasattr(main, '_search_engine'):
                    main._search_engine = HybridSearchEngine(collection)

                domain = filter_metadata.get("domain") if filter_metadata else None
                results = main._search_engine.search(
                    query=question,
                    n_results=3,
                    domain=domain,
                    method="hybrid"
                )

                elapsed = time.time() - start
                print(f"✅ Found {len(results)} relevant documents ({elapsed:.2f}s)\n")

                # Display sources with full content
                print(f"📚 Retrieved Documents:")
                print("="*60)
                for i, result in enumerate(results, 1):
                    metadata = result['metadata']
                    doc = result['document']

                    print(f"\n{i}. ", end="")
                    if metadata.get('source_type') == 'csv':
                        print(f"{metadata.get('source', 'Unknown')} (Row {metadata.get('row_id', 'N/A')})")
                        print(f"   Brand: {metadata.get('brand', 'N/A')} | Category: {metadata.get('category', 'N/A')} | Price: {metadata.get('sell_price', 'N/A')}")
                    else:
                        print(f"{metadata.get('source', 'Unknown')} (Page {metadata.get('page', 'N/A')})")

                    print(f"\n   Content:")
                    print(f"   {'-'*56}")
                    # Show first 500 characters of each chunk
                    preview = doc[:500] if len(doc) > 500 else doc
                    for line in preview.split('\n'):
                        print(f"   {line}")
                    if len(doc) > 500:
                        print(f"   ... ({len(doc) - 500} more characters)")
                    print()

            else:
                # Full mode: Use RAG pipeline with LLM
                result = ask_question(
                    collection,
                    question,
                    n_results=3,
                    filter_metadata=filter_metadata,
                    use_reranking=use_reranking
                )

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
