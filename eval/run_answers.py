"""
Generate answers for the human-review subset and write a blinded review sheet.

    python -m eval.run_answers --split test --final            (the 12 held-out review questions)
    python -m eval.run_answers --ids D01 V07                   (named development questions, harness check)

Two configurations, both the application's own paths with n_results=3:
    hybrid_prod3   hybrid search for 3 results, no reranking
    hybrid_rerank  hybrid search for 9 candidates, reranked to 3
The prompt, the source list and the citation marking come from rag.qa_chain. The only
difference from the application's generation call is the sampling setting: temperature 0 and
seed 0 here (the application uses temperature 0.7), so the run can be repeated.

Outputs, in eval/results/:
    answers_<time>.jsonl        full records, including the configuration
    review_<time>.csv           the sheet to fill in; shuffled, configuration hidden
    review_key_<time>.json      maps sheet items back to question and configuration
"""

import argparse
import csv
import json
import random

import requests

from eval import environment, guard, ground_truth as gt, sources
from eval.build_index import INDEX_DIR
from eval.run_retrieval import retrieve
from rag import config
from rag.qa_chain import NO_ANSWER, build_prompt, format_sources, mark_cited, warm_up_model
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.retrieval.vector_store import get_chroma_client

CONFIGS = ["hybrid_prod3", "hybrid_rerank"]
GENERATION_OPTIONS = {"temperature": 0, "seed": 0, "num_predict": 150}


def generate(prompt: str) -> str:
    response = requests.post(f"{config.OLLAMA_URL}/api/generate", timeout=180, json={
        "model": config.LLM_MODEL, "prompt": prompt, "stream": False, "options": GENERATION_OPTIONS})
    response.raise_for_status()
    return response.json()["response"].strip()


def describe_source(source: dict, rows: list) -> str:
    if source["source_type"] == "pdf":
        return f"{gt.pdf_stem(source['source'])} PDF page {source['page']}"
    row = rows[int(source["row_id"])]
    return f"EPA id {row['id']}: {row['year']} {row['make']} {row['model']}"


def gold_text(question: dict, rows: list) -> str:
    if question["domain"] == "technical":
        if not question["gold_spans"]:
            return "(none: not answerable from the data)"
        return "\n".join(f"{s['doc']} PDF page {s['page']}: {s['text']}" for s in question["gold_spans"])
    if not question["answerable"]:
        return "(none: not answerable from the data)"
    by_id = {r["id"]: r for r in rows}
    examples = ", ".join(f"{by_id[i]['make']} {by_id[i]['model']} (comb08={by_id[i]['comb08']})"
                         for i in question["gold_rows"][:6])
    text = f"Rule: {question['gold_rule']}. {len(question['gold_rows'])} matching rows, e.g. {examples}"
    if "expected" in question:
        text += f". Exact answer from the data: {question['expected']}"
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["test"], help="use the answer-review subset of the held-out split")
    parser.add_argument("--ids", nargs="+", help="run these question ids instead (development questions)")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--allow-rerun", action="store_true")
    args = parser.parse_args()
    if not args.split and not args.ids:
        parser.error("give --split test or --ids")

    all_questions = gt.load_questions()
    if args.ids:
        selected = [q for q in all_questions if q["id"] in args.ids]
    else:
        selected = [q for q in all_questions if q["answer_review"] and q["split"] == "test"]
    environment_info = environment.describe_environment()
    touches_test = any(q["split"] == "test" for q in selected)
    guard.check_split("test" if touches_test else "dev", args.final, args.allow_rerun, "answers",
                      environment_info["git_commit"])

    engine = HybridSearchEngine(get_chroma_client(INDEX_DIR).get_collection(config.COLLECTION_NAME))
    rows = gt.load_vehicle_rows()
    warm_up_model(model=config.LLM_MODEL, timeout=120)
    engine.search("warm up", 3, method="semantic")

    records = []
    for q in selected:
        for name in CONFIGS:
            results = retrieve(engine, name, q["question"], q["domain"])
            chunks = [r["document"] for r in results]
            metas = [r["metadata"] for r in results]
            answer = generate(build_prompt(q["question"], chunks)) if chunks else NO_ANSWER
            source_list = mark_cited(answer, format_sources(chunks, metas))
            records.append({"id": q["id"], "config": name, "answer": answer,
                            "sources": source_list, "question": q})
            print(f"{q['id']} {name} done")

    sources.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = environment_info["timestamp_utc"].replace(":", "").replace("-", "")[:15]
    (sources.RESULTS_DIR / f"answers_{stamp}.jsonl").write_text(
        "\n".join(json.dumps({**r, "environment": environment_info if i == 0 else None, "generation": GENERATION_OPTIONS},
                             ensure_ascii=False) for i, r in enumerate(records)))

    order = list(range(len(records)))
    random.Random(0).shuffle(order)
    key, sheet = {}, []
    for item, index in enumerate(order, 1):
        r = records[index]
        q = r["question"]
        cited = [describe_source(s, rows) for s in r["sources"] if s["cited"]]
        others = [describe_source(s, rows) for s in r["sources"] if not s["cited"]]
        key[item] = {"id": r["id"], "config": r["config"], "category": q["category"], "domain": q["domain"]}
        sheet.append({"item": item, "question": q["question"], "reference_answer": q["answer"],
                      "gold_evidence": gold_text(q, rows), "system_answer": r["answer"],
                      "cited_sources": "\n".join(cited) or "(none)",
                      "other_retrieved_sources": "\n".join(others) or "(none)",
                      "correctness_0_1_2": "", "attribution_0_1_2": "", "notes": ""})
    with open(sources.RESULTS_DIR / f"review_{stamp}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sheet[0].keys()))
        writer.writeheader()
        writer.writerows(sheet)
    (sources.RESULTS_DIR / f"review_key_{stamp}.json").write_text(json.dumps(key, indent=2))
    print(f"wrote answers_{stamp}.jsonl, review_{stamp}.csv, review_key_{stamp}.json in {sources.RESULTS_DIR}")


if __name__ == "__main__":
    main()
