"""
Compare retrieval configurations on the evaluation questions. No answers are generated here,
except that the reranking configuration calls the local LLM to reorder candidates.

    python -m eval.build_index                              (once)
    python -m eval.run_retrieval --split dev                (development questions)
    python -m eval.run_retrieval --split test --final       (held-out questions, once)

Configurations
    bm25           keyword search only, top 10
    vector         embedding search only, top 10
    hybrid         BM25 + vector with Reciprocal Rank Fusion, top 10
    hybrid_prod3   the application's no-reranking path: hybrid search for 3 results
    hybrid_rerank  the application's reranking path: hybrid search for 9 candidates,
                   reordered by the local LLM, top 3
Only the last two are directly comparable (both return 3 results the way the application does).
Every query uses the domain filter that matches the question's domain.
"""

import argparse
import json
import statistics
import time
from collections import defaultdict

from eval import environment, guard, ground_truth as gt, metrics, sources
from eval.build_index import INDEX_DIR
from rag import config
from rag.qa_chain import warm_up_model
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.reranker import rerank_chunks
from rag.retrieval.vector_store import get_chroma_client

CONFIGS = ["bm25", "vector", "hybrid", "hybrid_prod3", "hybrid_rerank"]
SHORT_LIST = {"hybrid_prod3", "hybrid_rerank"}  # return only 3 results, so only k <= 3 is meaningful
HEADLINE = {
    "technical (exact, paraphrase, multi_doc)": lambda q: q["domain"] == "technical" and q["answerable"],
    "vehicles (exact, semantic)": lambda q: q["domain"] == "vehicles" and q["category"] in ("exact", "semantic"),
    "vehicles structured (informational)": lambda q: q["domain"] == "vehicles" and q["category"] == "structured",
}


def retrieve(engine, name: str, question: str, domain: str):
    """Run one configuration and return the list of {document, metadata}."""
    if name == "bm25":
        return engine.search(question, 10, domain=domain, method="bm25")
    if name == "vector":
        return engine.search(question, 10, domain=domain, method="semantic")
    if name == "hybrid":
        return engine.search(question, 10, domain=domain, method="hybrid")
    if name == "hybrid_prod3":
        return engine.search(question, 3, domain=domain, method="hybrid")
    if name == "hybrid_rerank":
        candidates = engine.search(question, 9, domain=domain, method="hybrid")
        chunks, metas = rerank_chunks(question, [c["document"] for c in candidates],
                                      [c["metadata"] for c in candidates], top_k=3, method="ollama")
        return [{"document": c, "metadata": m} for c, m in zip(chunks, metas)]
    raise ValueError(name)


def identifier(result: dict) -> str:
    meta = result["metadata"]
    if meta.get("source_type") == "pdf":
        return gt.chunk_key(meta["source"], meta["page"], result["document"])
    return meta["row_id"]


def score(question: dict, ranked: list, gold, name: str, loose=None) -> dict:
    """
    Metrics for one question. For vehicle questions, `loose` is the set of rows that satisfy
    the rule in any model year; its metrics are prefixed "loose_". The baseline row text has no
    model-year field, so the loose numbers show how well the right kind of vehicle was found.
    """
    ks = [k for k in metrics.KS if k <= (3 if name in SHORT_LIST else 10)]
    if question["domain"] == "technical":
        values = metrics.evidence_metrics(ranked, gold, ks)
    else:
        values = metrics.set_metrics(ranked, gold, ks)
        if loose is not None:
            values.update({f"loose_{k}": v for k, v in metrics.set_metrics(ranked, loose, ks).items()})
    if name in SHORT_LIST:
        values.pop("mrr@10", None)
    return values


def aggregate(per_question: list) -> dict:
    out = {}
    for group, selector in HEADLINE.items():
        out[group] = {}
        for name in CONFIGS:
            rows = [r for r in per_question if selector(r["question"]) and name in r["configs"]]
            if not rows:
                continue
            keys = sorted({k for r in rows for k in r["configs"][name]["metrics"]})
            entry = {"questions": len(rows)}
            for key in keys:
                values = [r["configs"][name]["metrics"][key] for r in rows if key in r["configs"][name]["metrics"]]
                entry[key] = round(metrics.mean(values), 4)
            latencies = [r["configs"][name]["latency_ms"] for r in rows]
            entry["latency_ms_median"] = round(statistics.median(latencies), 1)
            entry["latency_ms_p95"] = round(metrics.percentile(latencies, 95), 1)
            out[group][name] = entry
    return out


SHOWN = {
    "technical": ["span_recall@1", "span_recall@3", "span_recall@10", "mrr@10", "mrr@3"],
    "vehicles": ["precision@3", "precision@10", "mrr@10", "mrr@3", "loose_precision@3", "loose_precision@10", "loose_mrr@10", "loose_mrr@3"],
}


def print_table(aggregated: dict) -> None:
    for group, by_config in aggregated.items():
        print(f"\n== {group}")
        wanted = SHOWN["technical" if group.startswith("technical") else "vehicles"]
        for name, entry in by_config.items():
            shown = [f"{k}={entry[k]}" for k in wanted if k in entry]
            shown += [f"latency_ms median={entry['latency_ms_median']} p95={entry['latency_ms_p95']}"]
            print(f"  {name:14s} n={entry['questions']:<3d} " + "  ".join(shown))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "test", "all"], required=True)
    parser.add_argument("--final", action="store_true", help="required for splits that include held-out questions")
    parser.add_argument("--allow-rerun", action="store_true")
    parser.add_argument("--repeats", type=int, default=3, help="timed repetitions per query and configuration")
    parser.add_argument("--configs", nargs="+", choices=CONFIGS, default=CONFIGS)
    args = parser.parse_args()

    environment_info = environment.describe_environment()
    guard.check_split(args.split, args.final, args.allow_rerun, "retrieval", environment_info["git_commit"])

    questions = [q for q in gt.load_questions(args.split) if q["category"] != "unanswerable"]
    client = get_chroma_client(INDEX_DIR)
    collection = client.get_collection(config.COLLECTION_NAME)
    engine = HybridSearchEngine(collection)
    if "hybrid_rerank" in args.configs:
        warm_up_model(model=config.LLM_MODEL, timeout=120)

    pages, chunks = gt.load_page_texts(), gt.load_pdf_chunks()
    rows = gt.load_vehicle_rows()
    row_id = {r["id"]: str(i) for i, r in enumerate(rows)}

    # warm the embedding model so the first timed query is not a load
    engine.search("warm up", 3, method="semantic")

    per_question = []
    for q in questions:
        loose = None
        if q["domain"] == "technical":
            gold = gt.gold_chunk_keys(q, chunks, pages)
        else:
            gold = {row_id[i] for i in q["gold_rows"]}
            loose_rule = [c for c in q["gold_rule"] if c[0] != "year"]
            loose = {row_id[r["id"]] for r in gt.rows_for_rule(rows, loose_rule)}
        entry = {"question": {k: q[k] for k in ("id", "split", "domain", "category", "question", "answerable")}, "configs": {}}
        for name in args.configs:
            timings, ranked = [], None
            for repeat in range(args.repeats):
                started = time.perf_counter()
                results = retrieve(engine, name, q["question"], q["domain"])
                timings.append((time.perf_counter() - started) * 1000)
                if ranked is None:
                    ranked = [identifier(r) for r in results]
            entry["configs"][name] = {
                "ranked": ranked,
                "metrics": score(q, ranked, gold, name, loose),
                "latency_ms": statistics.median(timings),
                "latency_ms_all": [round(t, 1) for t in timings],
            }
        per_question.append(entry)
        print(f"{q['id']} done")

    aggregated = aggregate(per_question)
    sources.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = environment_info["timestamp_utc"].replace(":", "").replace("-", "")[:15]
    out_path = sources.RESULTS_DIR / f"retrieval_{args.split}_{stamp}.json"
    out_path.write_text(json.dumps({
        "environment": environment_info,
        "arguments": vars(args),
        "aggregate": aggregated,
        "per_question": per_question,
    }, indent=2))
    print_table(aggregated)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
