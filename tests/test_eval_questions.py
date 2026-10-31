"""
Checks on the evaluation question file and ground-truth helpers (eval/).

These need no network and no model. Tests that need the NIST PDFs are skipped when the
PDFs have not been downloaded (python -m eval.fetch_data nist).
"""
import collections

import pytest

from eval import fetch_data, ground_truth as gt, guard, sources

QUESTIONS = gt.load_questions()
PDFS_PRESENT = all((sources.NIST_DIR / name).exists() for name in sources.NIST_FILES)
needs_pdfs = pytest.mark.skipif(not PDFS_PRESENT, reason="NIST PDFs not downloaded: python -m eval.fetch_data nist")


def test_question_set_has_the_designed_shape():
    assert len(QUESTIONS) == 30
    assert len({q["id"] for q in QUESTIONS}) == 30
    assert collections.Counter(q["split"] for q in QUESTIONS) == {"dev": 10, "test": 20}
    review = [q for q in QUESTIONS if q["answer_review"]]
    assert len(review) == 12
    assert all(q["split"] == "test" for q in review)


def test_every_category_is_present_in_both_domains():
    counts = collections.Counter((q["domain"], q["category"]) for q in QUESTIONS)
    assert counts[("technical", "multi_doc")] == 3
    assert counts[("technical", "unanswerable")] == 3
    assert counts[("vehicles", "structured")] == 4
    assert counts[("vehicles", "unanswerable")] == 2


def test_dev_split_covers_every_kind_of_question():
    dev = {(q["domain"], q["category"]) for q in QUESTIONS if q["split"] == "dev"}
    assert ("vehicles", "structured") in dev and ("technical", "multi_doc") in dev
    assert ("technical", "unanswerable") in dev and ("vehicles", "unanswerable") in dev


def test_epa_snapshot_matches_its_pinned_checksum():
    assert fetch_data.sha256_of(sources.EPA_SNAPSHOT) == sources.EPA_SNAPSHOT_SHA256


def test_snapshot_only_has_the_selected_model_years():
    rows = gt.load_vehicle_rows()
    assert len(rows) == 2607
    assert {r["year"] for r in rows} == set(sources.EPA_YEARS)


@pytest.mark.parametrize("question", [q for q in QUESTIONS if q["domain"] == "vehicles" and q["answerable"]],
                         ids=lambda q: q["id"])
def test_vehicle_gold_rows_and_aggregates_match_the_rule(question):
    rows = gt.load_vehicle_rows()
    matched = gt.rows_for_rule(rows, question["gold_rule"])
    assert [r["id"] for r in matched] == question["gold_rows"]
    assert matched, "an answerable question needs at least one gold row"
    if "aggregate" in question:
        assert gt.aggregate(matched, question["aggregate"]) == question["expected"]


@pytest.mark.parametrize("question", [q for q in QUESTIONS if q["domain"] == "vehicles" and not q["answerable"]],
                         ids=lambda q: q["id"])
def test_unanswerable_vehicle_questions_have_no_matching_column(question):
    columns = [c.lower() for c in gt.load_vehicle_rows()[0]]
    assert not [c for c in columns if any(t.lower() in c for t in question["absent_columns"])]


@needs_pdfs
def test_nist_pdfs_match_their_pinned_checksums():
    for name, expected in sources.NIST_FILES.items():
        assert fetch_data.sha256_of(sources.NIST_DIR / name) == expected


@needs_pdfs
def test_every_gold_span_is_verbatim_on_its_page_and_covered_by_a_chunk():
    pages, chunks = gt.load_page_texts(), gt.load_pdf_chunks()
    for q in (q for q in QUESTIONS if q["domain"] == "technical" and q["answerable"]):
        for span in q["gold_spans"]:
            assert gt.span_offsets(pages[(span["doc"], span["page"] - 1)], span["text"]), (q["id"], span["text"][:50])
        assert all(gt.gold_chunk_keys(q, chunks, pages)), q["id"]


@needs_pdfs
def test_topics_of_unanswerable_document_questions_are_absent():
    corpus = " ".join(gt.normalize(t) for t in gt.load_page_texts().values()).lower()
    for q in (q for q in QUESTIONS if q["domain"] == "technical" and not q["answerable"]):
        assert not [t for t in q["absent_terms"] if t.lower() in corpus], q["id"]


# ---- chunk coverage rule ------------------------------------------------------

def test_a_chunk_must_contain_half_of_the_span():
    assert gt.covers_span((0, 100), (10, 60))
    assert gt.covers_span((0, 35), (10, 60))        # 25 of 50 characters
    assert not gt.covers_span((0, 30), (10, 60))    # 20 of 50 characters
    assert not gt.covers_span((100, 200), (10, 60))


# ---- held-out guard ------------------------------------------------------------

@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "LEDGER", tmp_path / "test_runs.log")
    monkeypatch.setattr(sources, "RESULTS_DIR", tmp_path)
    return tmp_path / "test_runs.log"


def test_dev_split_is_never_blocked_or_logged(ledger):
    guard.check_split("dev", False, False, "retrieval", "abc")
    assert not ledger.exists()


def test_held_out_split_needs_the_final_flag(ledger):
    with pytest.raises(SystemExit):
        guard.check_split("test", False, False, "retrieval", "abc")


def test_held_out_run_is_logged_and_a_second_run_needs_permission(ledger):
    guard.check_split("test", True, False, "retrieval", "abc123")
    assert "purpose=retrieval" in ledger.read_text() and "abc123" in ledger.read_text()
    with pytest.raises(SystemExit):
        guard.check_split("test", True, False, "retrieval", "abc123")
    guard.check_split("test", True, False, "answers", "abc123")       # a different purpose is separate
    guard.check_split("test", True, True, "retrieval", "abc123")      # explicit rerun is allowed
    assert len(ledger.read_text().splitlines()) == 3
