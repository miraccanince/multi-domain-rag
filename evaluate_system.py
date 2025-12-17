#!/usr/bin/env python3
"""
Simple RAG System Evaluation
Tests FlexiRAG with sample questions and provides basic metrics.
"""

from src.vector_store import initialize_chroma_db
from src.qa_chain import ask_question
from src.embeddings import get_embedding_model, calculate_similarity
import time

# Test cases
TEST_CASES = {
    "automotive": [
        {
            "question": "What is CAN protocol used for?",
            "keywords": ["vehicle", "bus", "standard", "communication", "controller", "network"]
        },
        {
            "question": "What does OBD-II stand for?",
            "keywords": ["on-board", "diagnostics", "obd", "vehicle"]
        },
        {
            "question": "What is CAN FD?",
            "keywords": ["can fd", "flexible", "data", "rate", "bytes"]
        }
    ],
    "fashion": [
        {
            "question": "What types of women's clothing are available?",
            "keywords": ["western", "indian", "dress", "wear", "women", "clothing"]
        },
        {
            "question": "Are there products under 1000 rupees?",
            "keywords": ["price", "rupees", "1000", "product", "sell"]
        }
    ]
}


def calculate_keyword_coverage(answer, keywords):
    """
    Calculate what percentage of keywords appear in the answer.
    Simple metric for answer quality.
    """
    answer_lower = answer.lower()
    matched = sum(1 for kw in keywords if kw in answer_lower)
    return matched / len(keywords) if keywords else 0


def evaluate_domain(collection, domain_name, test_cases):
    """Evaluate all test cases for a domain."""
    print(f"\n{'='*60}")
    print(f"Testing Domain: {domain_name.upper()}")
    print(f"{'='*60}")

    results = []
    filter_metadata = {"domain": domain_name}

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['question']}")
        print("-" * 60)

        start_time = time.time()

        try:
            result = ask_question(
                collection,
                test['question'],
                n_results=3,
                filter_metadata=filter_metadata
            )

            elapsed = time.time() - start_time
            answer = result['answer']

            # Calculate metrics
            keyword_score = calculate_keyword_coverage(answer, test['keywords'])
            has_answer = len(answer) > 50  # Basic check
            chunk_count = len(result['retrieved_chunks'])

            # Check if answer says "don't have information"
            is_failure = "don't have" in answer.lower() or "not in the context" in answer.lower()

            results.append({
                "question": test['question'],
                "success": has_answer and not is_failure,
                "keyword_coverage": keyword_score,
                "chunks_retrieved": chunk_count,
                "response_time": elapsed,
                "answer_length": len(answer)
            })

            # Display result
            status = "✅" if (has_answer and not is_failure and keyword_score > 0.3) else "⚠️"
            print(f"{status} Keyword Coverage: {keyword_score:.1%}")
            print(f"   Retrieved Chunks: {chunk_count}")
            print(f"   Response Time: {elapsed:.2f}s")
            print(f"   Answer Preview: {answer[:150]}...")

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "question": test['question'],
                "success": False,
                "keyword_coverage": 0,
                "chunks_retrieved": 0,
                "response_time": 0,
                "answer_length": 0
            })

    return results


def print_summary(all_results):
    """Print evaluation summary."""
    print(f"\n\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")

    for domain_name, results in all_results.items():
        print(f"\n📊 {domain_name.upper()} Domain:")
        print("-" * 60)

        total = len(results)
        successful = sum(1 for r in results if r['success'])
        avg_keyword = sum(r['keyword_coverage'] for r in results) / total if total > 0 else 0
        avg_time = sum(r['response_time'] for r in results) / total if total > 0 else 0
        avg_chunks = sum(r['chunks_retrieved'] for r in results) / total if total > 0 else 0

        print(f"Total Tests: {total}")
        print(f"Successful: {successful}/{total} ({successful/total*100:.0f}%)")
        print(f"Avg Keyword Coverage: {avg_keyword:.1%}")
        print(f"Avg Response Time: {avg_time:.2f}s")
        print(f"Avg Chunks Retrieved: {avg_chunks:.1f}")

        if successful / total >= 0.8:
            grade = "🏆 Excellent"
        elif successful / total >= 0.6:
            grade = "✅ Good"
        elif successful / total >= 0.4:
            grade = "⚠️  Fair"
        else:
            grade = "❌ Needs Improvement"

        print(f"Grade: {grade}")

    # Overall
    all_tests = [r for results in all_results.values() for r in results]
    total_all = len(all_tests)
    successful_all = sum(1 for r in all_tests if r['success'])

    print(f"\n🎯 Overall Performance:")
    print("-" * 60)
    print(f"Total Tests: {total_all}")
    print(f"Success Rate: {successful_all}/{total_all} ({successful_all/total_all*100:.0f}%)")

    overall_score = successful_all / total_all if total_all > 0 else 0
    print(f"\n⭐ Overall Score: {overall_score:.1%}")


def main():
    print("="*60)
    print("FlexiRAG System Evaluation")
    print("="*60)

    # Initialize
    print("\n🔄 Initializing ChromaDB...")
    client, collection = initialize_chroma_db()
    doc_count = collection.count()
    print(f"✅ Loaded {doc_count:,} documents")

    # Get domains
    from src.vector_store import get_available_domains
    domains = get_available_domains(collection)
    print(f"✅ Found {len(domains)} domains: {', '.join(domains.keys())}")

    # Run tests
    all_results = {}
    for domain_name, test_cases in TEST_CASES.items():
        if domain_name in domains:
            results = evaluate_domain(collection, domain_name, test_cases)
            all_results[domain_name] = results
        else:
            print(f"\n⚠️  Domain '{domain_name}' not found in database, skipping...")

    # Summary
    print_summary(all_results)

    print(f"\n{'='*60}")
    print("✅ Evaluation Complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
