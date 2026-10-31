"""
Check the question file against the source data. Run before any evaluation:

    python -m eval.validate_questions

It verifies that
  * the NIST PDFs and the EPA snapshot match their pinned SHA-256 values,
  * every gold span occurs verbatim on the stated PDF page,
  * every gold span is covered by at least one chunk of the application's chunker,
  * every vehicle gold row list and expected aggregate matches a recomputation from the rule,
  * the topic of every unanswerable question is absent from the data,
  * the split and review-subset sizes are as designed.
"""

import collections
import sys

from eval import fetch_data, ground_truth as gt, sources


def main() -> int:
    errors = []
    questions = gt.load_questions()

    if not fetch_data.verify():
        errors.append("data files do not match their pinned SHA-256 values")

    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        errors.append("duplicate question ids")
    splits = collections.Counter(q["split"] for q in questions)
    review = [q for q in questions if q["answer_review"]]
    print(f"{len(questions)} questions, splits {dict(splits)}, answer-review subset {len(review)}")
    if len(questions) != 30 or splits != {"dev": 10, "test": 20} or len(review) != 12:
        errors.append("expected 30 questions, 10 dev and 20 test, 12 in the review subset")
    if any(q["split"] != "test" for q in review):
        errors.append("the answer-review subset must come from the held-out test split")
    print("categories:", dict(collections.Counter((q["domain"], q["category"]) for q in questions)))

    pages = gt.load_page_texts()
    chunks = gt.load_pdf_chunks()
    corpus = " ".join(gt.normalize(t) for t in pages.values()).lower()
    unmapped = [c for c in chunks if gt.chunk_offsets(pages[(gt.pdf_stem(c.metadata["source"]), c.metadata["page"])], c.page_content) is None]
    if unmapped:
        errors.append(f"{len(unmapped)} chunks cannot be located in their page text")
    print(f"{len(chunks)} PDF chunks from the application's chunker")

    rows = gt.load_vehicle_rows()
    print(f"{len(rows)} vehicle rows in the snapshot")
    columns = [c.lower() for c in rows[0].keys()]

    for q in questions:
        tag = q["id"]
        if q["domain"] == "technical":
            for span in q["gold_spans"]:
                page_text = pages.get((span["doc"], span["page"] - 1))
                if page_text is None or gt.span_offsets(page_text, span["text"]) is None:
                    errors.append(f"{tag}: span not found on {span['doc']} page {span['page']}: {span['text'][:60]}")
            if q["answerable"]:
                per_span = gt.gold_chunk_keys(q, chunks, pages)
                if any(not keys for keys in per_span):
                    errors.append(f"{tag}: a gold span is not covered by any chunk")
                print(f"  {tag} {q['category']:12s} spans={len(q['gold_spans'])} chunks per span={[len(k) for k in per_span]}")
            else:
                for term in q.get("absent_terms", []):
                    if term.lower() in corpus:
                        errors.append(f"{tag}: unanswerable question but '{term}' occurs in the documents")
                print(f"  {tag} unanswerable, absent terms {q.get('absent_terms')}")
        else:
            if q["answerable"]:
                matched = gt.rows_for_rule(rows, q["gold_rule"])
                if [r["id"] for r in matched] != q["gold_rows"]:
                    errors.append(f"{tag}: gold rows differ from the rule")
                if "aggregate" in q and gt.aggregate(matched, q["aggregate"]) != q["expected"]:
                    errors.append(f"{tag}: expected aggregate differs from recomputation")
                print(f"  {tag} {q['category']:12s} gold rows={len(q['gold_rows'])} expected={q.get('expected', '-')}")
            else:
                clash = [c for c in columns if any(t.lower() in c for t in q.get("absent_columns", []))]
                if clash:
                    errors.append(f"{tag}: columns exist that could answer it: {clash}")
                print(f"  {tag} unanswerable, absent columns {q.get('absent_columns')}")

    if errors:
        print("\nPROBLEMS:")
        for e in errors:
            print(" -", e)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
