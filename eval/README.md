# Evaluation

A small evaluation of the retrieval and answer pipeline on two domains with different shapes:
technical PDFs and product-like records. It is separate from the application code: nothing in
`rag/`, `api/` or `scripts/` imports it. It measures the application as it is, with the
application's own ingestion, so the first results describe the baseline representation.

Status: the question set and tooling are built and validated. The retrieval benchmark was run once on
31 October 2026 on all 30 questions; the summary is in the main [README](../README.md#results-and-evaluation)
and the raw output is `results/retrieval_all_20261031T221011.json`. The answer review has not been done.

## Data

| Domain | Data | Size |
|--------|------|------|
| `technical` | NIST SP 800-40r4, 800-61r3, 800-63B-4, 800-88r2 (PDF) | 253 pages, 797 chunks |
| `vehicles` | EPA fuel economy records, model years 2023 and 2024 (CSV snapshot) | 2,607 rows, 84 columns |

URLs, license notes and full SHA-256 values are in [SOURCES.md](SOURCES.md). The snapshot is committed;
the PDFs are downloaded by script.

## Commands, in order

```bash
python -m eval.fetch_data nist            # download the PDFs and verify checksums
python -m eval.validate_questions         # check every gold span, row and rule against the data
python -m eval.build_index                # index both domains with the application's own ingestion
python -m eval.run_retrieval --split dev  # development questions; repeat freely
python -m eval.run_retrieval --split test --final   # held-out questions; run once
python -m eval.run_answers --split test --final     # answers for the 12 review questions
# fill in eval/results/review_<time>.csv by hand, then:
python -m eval.summarize_review eval/results/review_<time>.csv eval/results/review_key_<time>.json
```

Needs a local Ollama with `llama3.2:3b` (only for the reranking configuration and answer generation) and
the sentence-transformers model (downloaded on first use). Results are written to `eval/results/`, and every
run records its environment (versions, model details, data checksums, git commit, whether the working tree
had uncommitted changes).

## Questions

[questions.jsonl](questions.jsonl) has 30 questions, one JSON object per line.

| Domain | exact | paraphrase / semantic | multi-document | structured | unanswerable |
|--------|-------|-----------------------|----------------|------------|--------------|
| technical | 6 | 6 | 3 | - | 3 |
| vehicles | 2 | 4 | - | 4 | 2 |

* Exact: the question uses the document's own terms. Paraphrase or semantic: it does not.
* Multi-document: the answer needs evidence from two publications.
* Structured: needs counting, a maximum, an average or a numeric filter over rows. These are kept apart
  from the semantic questions because they test a different capability.
* Unanswerable: the answer is not in the data; the correct behavior is to say so.

### Splits

* `dev` (10 questions): may be used to find problems and decide on changes.
* `test` (20 questions): held out. Retrieval and ranking settings must not be changed after looking at test
  results. `eval/guard.py` requires `--final` for the test split and writes every run to
  `eval/results/test_runs.log`; a second run for the same purpose needs `--allow-rerun`.
* The 12 questions for human answer review (`answer_review: true`) are all from the test split: 2 exact,
  3 paraphrase or semantic, 2 multi-document, 2 unanswerable, 3 structured.

Decisions made before this evaluation, and what they were based on: raising the generation context limit to
1000 characters and the reranker preview to 1000 characters, the BM25 tokenizer, and citation marking were
based on smoke-test questions that are not in this question set ("What is a CAN error frame?", "What is the
capital of France?", "Which products are waterproof?").

## Ground truth

Every question has a reference answer. Evidence is stored so that it does not depend on how the text is
chunked.

* Technical questions: `gold_spans`, a list of `{doc, page, text}`. `page` is the 1-based PDF page and `text`
  is a verbatim span (whitespace is normalized when comparing). `validate_questions` checks that each span
  occurs on that page. A chunk counts as evidence for a span when it contains at least half of the span's
  characters, so a span cut by a chunk boundary is still covered. `validate_questions` also checks that every
  span is covered by at least one chunk produced by the application's chunker.
* Vehicle questions: `gold_rule`, a list of `[column, operator, value]` conditions over the EPA columns, and
  `gold_rows`, the EPA `id` values of all matching rows. The validator recomputes the rows from the rule.
  Structured questions also have an `aggregate` and the `expected` exact answer, recomputed the same way.
* Unanswerable questions: `absent_terms` (documents) or `absent_columns` (vehicles). The validator checks
  that the terms occur nowhere in the PDFs and that no column could hold the answer.

The spans and rules were written by hand from the source text and are checked mechanically against it, not
produced by a language model. Reference answers are short statements of what the evidence says. They have
not been read by a second person.

## Retrieval configurations and metrics

Configurations (see `eval/run_retrieval.py`): `bm25`, `vector`, `hybrid` (RRF), each returning 10 results;
`hybrid_prod3` (the application's no-reranking path, 3 results); `hybrid_rerank` (the application's reranking
path: 9 hybrid candidates reordered by the local LLM, 3 results). Only the last two are directly comparable.
Every query is filtered to the question's domain.

| Question type | Metrics |
|---------------|---------|
| Technical (evidence spans) | span recall@1/3/5/10 (share of gold spans covered by the top k chunks), MRR@10 |
| Vehicles, exact and semantic (gold row sets) | precision@k, capped recall@k (gold rows found / min(gold rows, k)), hit@k, MRR@10 |
| Vehicles, structured | the same set metrics, reported separately and marked informational |
| Unanswerable | no retrieval metrics; judged in the answer review |

For vehicle questions each metric is also computed without the model-year condition (prefix `loose_`),
because the baseline row text has no year field (see below). Latency is wall time per query, the median of
`--repeats` runs per query, summarized as the median and 95th percentile over questions. For `hybrid_rerank`
it includes the LLM call. Latency values depend on the machine and are only comparable within one run.

## Human review of answers

`run_answers` generates answers for the 12 review questions with `hybrid_prod3` and `hybrid_rerank`, using
the application's prompt, source list and citation marking. Generation uses temperature 0 and seed 0, which
differs from the application's temperature 0.7 so the run can be repeated. The review sheet is shuffled and
does not show the configuration. Each item is scored by hand, with no language model judge:

* Correctness: 2 = correct and complete, 1 = partly correct or incomplete, 0 = wrong, or an answer given
  where the question is unanswerable. For an unanswerable question, a refusal scores 2. For a structured
  question, 2 requires the exact value in `expected` (or the exact list).
* Attribution: 2 = every cited source supports the answer, 1 = some do, 0 = none do or the answer cites
  nothing. Leave it empty when it does not apply (a refusal).

## Baseline representation

The first runs use the application's ingestion unchanged. Facts about it that affect the results:

* PDFs: 1000-character chunks with 200 characters of overlap; each chunk keeps its file and page.
* Vehicles: the CSV loader writes one document per row. The document text contains only the non-numeric
  columns, as `name: value` lines (for example `make`, `model`, `VClass`, `fuelType`, `trany`, `drive`,
  `eng_dscr`, `createdOn`, `modifiedOn`). The numeric columns (model year, MPG, annual fuel cost, CO2, range)
  are stored only as metadata. Retrieval and the language model never see them.
* The year therefore reaches the text only through the `createdOn` and `modifiedOn` date strings.
  Those correlate with the model year but are not the model year.
* BM25 breaks score ties by document position, and rows with equal scores are common here. Results on the
  vehicles domain should be read with the `loose_` metrics next to the strict ones.

Structured questions (counts, maxima, averages, numeric thresholds) ask for an operation over many rows. A
retrieval system returns a few passages, so it cannot reliably produce such an answer by design, and the
numeric columns are not in the text in the baseline. Whether the pipeline gets any of them right is measured,
not assumed: the review sheet scores them against the exact answer in `expected`.

## Not done

* The human answer review (`run_answers` and `summarize_review` exist but were not run).
* Enrichment of the text representation, and structured filtering. Both are out of scope.

## Tests

`pytest tests/test_eval_metrics.py tests/test_eval_questions.py` checks the metric functions, the question
file shape, the vehicle rules against the committed snapshot, the held-out guard and (when the PDFs are
downloaded) every gold span.
