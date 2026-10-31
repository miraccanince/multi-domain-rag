"""
Retrieval, reranking and generation through rag.qa_chain.ask_question.

MOCKED: the embedding model (deterministic fake vectors) and Ollama (FakeOllama,
which records prompts and returns canned text). REAL: PDF and CSV loading,
ChromaDB, BM25, Reciprocal Rank Fusion, the reranker's reply parsing, prompt
construction and source formatting. Nothing here shows that a real model
answers well.
"""
import pytest

from rag.qa_chain import ask_question, build_prompt, NO_ANSWER, LLM_ERROR_PREFIX


@pytest.fixture
def ask(example_index, fake_ollama):
    _, collection, engine = example_index

    def run(question, domain=None, method="bm25", rerank=False, n=3, **kw):
        return ask_question(
            collection, question, n_results=n,
            filter_metadata={"domain": domain} if domain else None,
            search_method=method, use_reranking=rerank,
            use_cache=False, stream=False, engine=engine, **kw)
    return run


# ---- ingestion to sources ------------------------------------------------

def test_pdf_answer_cites_file_and_page(ask, fake_ollama):
    result = ask("What is a CAN error frame?", domain="automotive")
    source = result["sources"][0]
    assert source["source_type"] == "pdf"
    assert source["source"] == "vehicle_diagnostics.pdf"
    assert source["page"] == 1
    assert result["answer"] == fake_ollama.answer
    assert "Controller Area Network" in fake_ollama.generate_prompts[0]


def test_csv_answer_cites_file_and_row(ask):
    result = ask("waterproof", domain="products", n=2)
    assert len(result["sources"]) == 2
    for source in result["sources"]:
        assert source["source_type"] == "csv"
        assert source["source"].endswith("catalog.csv")
        assert source["row_id"] != "N/A"
        assert "waterproof" in source["chunk_preview"].lower()


# ---- domain filtering ----------------------------------------------------

@pytest.mark.parametrize("method", ["semantic", "bm25", "hybrid"])
@pytest.mark.parametrize("domain,source_type", [("automotive", "pdf"), ("products", "csv")])
def test_domain_filter_holds_for_every_search_method(ask, method, domain, source_type):
    result = ask("brake boots waterproof frames", domain=domain, method=method)
    assert result["sources"]
    assert {s["source_type"] for s in result["sources"]} == {source_type}


def test_without_filter_both_domains_are_searched(ask):
    result = ask("waterproof messages", domain=None, method="bm25", n=10)
    assert {s["source_type"] for s in result["sources"]} == {"pdf", "csv"}


# ---- retrieval relevance (keyword side, deterministic) ---------------------

def test_keyword_retrieval_ranks_the_matching_row_first(ask):
    result = ask("floral dress", domain="products", n=3)
    assert "Floral Summer Dress" in result["sources"][0]["chunk_preview"]


# ---- reranking -----------------------------------------------------------

def candidates(engine, question, domain):
    return [r["document"] for r in engine.search(question, 3, domain=domain, method="bm25")]


def test_rerank_reorders_candidates_using_the_llm_reply(example_index, ask, fake_ollama):
    _, _, engine = example_index
    original = candidates(engine, "waterproof boots jacket", "products")
    assert len(original) == 3

    fake_ollama.rerank_reply = "3"
    result = ask("waterproof boots jacket", domain="products", rerank=True, n=1)

    assert len(fake_ollama.rerank_prompts) == 1
    assert result["retrieved_chunks"] == [original[2]]


def test_rerank_falls_back_to_retrieval_order_on_unparseable_reply(example_index, ask, fake_ollama):
    _, _, engine = example_index
    original = candidates(engine, "waterproof boots jacket", "products")

    fake_ollama.rerank_reply = "no idea"
    result = ask("waterproof boots jacket", domain="products", rerank=True, n=1)

    assert result["retrieved_chunks"] == [original[0]]


def test_rerank_ignores_out_of_range_numbers(example_index, ask, fake_ollama):
    _, _, engine = example_index
    original = candidates(engine, "waterproof boots jacket", "products")

    fake_ollama.rerank_reply = "99,2"
    result = ask("waterproof boots jacket", domain="products", rerank=True, n=2)

    assert result["retrieved_chunks"][0] == original[1]
    assert len(result["retrieved_chunks"]) == 2


def test_reranker_sees_text_beyond_300_characters(example_index, ask, fake_ollama):
    _, _, engine = example_index
    ask("error frame waterproof", rerank=True, n=1, method="hybrid")
    prompts = fake_ollama.rerank_prompts
    assert prompts and "it sends an error frame" in prompts[0]


# ---- empty and unanswerable queries ---------------------------------------

def test_keyword_search_with_no_matching_term_returns_nothing(example_index):
    _, _, engine = example_index
    assert engine.bm25_search("zebra quantum", 5) == []


def test_no_results_skips_the_llm(ask, fake_ollama):
    result = ask("zebra quantum", method="bm25")
    assert result["answer"] == NO_ANSWER
    assert result["sources"] == []
    assert fake_ollama.prompts == []


def test_unknown_domain_skips_the_llm(ask, fake_ollama):
    result = ask("anything", domain="does_not_exist", method="hybrid")
    assert result["answer"] == NO_ANSWER
    assert fake_ollama.prompts == []


def test_empty_collection_skips_the_llm(tmp_path, fake_embeddings, fake_ollama):
    from rag.retrieval.hybrid_search import HybridSearchEngine
    from rag.retrieval.vector_store import initialize_chroma_db
    _, empty = initialize_chroma_db(str(tmp_path / "empty"))
    result = ask_question(empty, "anything", search_method="hybrid", use_reranking=False,
                          use_cache=False, stream=False, engine=HybridSearchEngine(empty))
    assert result["answer"] == NO_ANSWER
    assert fake_ollama.prompts == []


def test_prompt_tells_the_model_to_refuse_without_context(ask, fake_ollama):
    ask("What is a CAN error frame?", domain="automotive")
    prompt = fake_ollama.generate_prompts[0]
    assert "ONLY" in prompt
    assert "I don't have enough information" in prompt


# ---- prompt construction --------------------------------------------------

def test_prompt_limits_chunk_count_and_length():
    chunks = ["a" * 1500, "b" * 1000, "c" * 1000, "d" * 1000]
    prompt = build_prompt("Q?", chunks)
    assert "[Document 3]" in prompt and "[Document 4]" not in prompt
    assert "a" * 1000 in prompt and "a" * 1001 not in prompt
    assert "Question: Q?" in prompt


def test_chunk_text_beyond_300_characters_reaches_the_prompt(ask, fake_ollama):
    """The sentence about error frames starts after character 600 of its chunk."""
    ask("What is a CAN error frame?", domain="automotive")
    assert "it sends an error frame" in fake_ollama.generate_prompts[0]


# ---- LLM failure ----------------------------------------------------------

def test_llm_down_returns_error_text_with_sources(ask, fake_ollama):
    fake_ollama.down = True
    result = ask("What is a CAN error frame?", domain="automotive", rerank=True)
    assert result["answer"].startswith(LLM_ERROR_PREFIX)
    assert result["sources"]


# ---- keyword search ignores common words ------------------------------------

def test_question_made_of_common_words_matches_nothing(example_index):
    _, _, engine = example_index
    assert engine.bm25_search("What is the capital of France?", 5) == []
    assert engine.bm25_search("what is the", 5) == []


def test_punctuation_does_not_block_a_keyword_match(example_index):
    _, _, engine = example_index
    # The PDF says "error frame." with a full stop, the question has none.
    results = engine.bm25_search("error frame", 3, domain="automotive")
    assert results and "error frame" in results[0]["document"]
    # Hyphenated terms are split the same way in documents and queries.
    assert engine.bm25_search("OBD-II", 3, domain="automotive")


# ---- sources: cited versus merely retrieved ----------------------------------

def test_only_documents_named_in_the_answer_are_marked_cited(ask, fake_ollama):
    fake_ollama.answer = "The frame is described in Document 2."
    result = ask("waterproof", domain="products", n=3, method="hybrid")
    assert [s["cited"] for s in result["sources"]] == [False, True, False]


@pytest.mark.parametrize("answer,expected", [
    ("See [Document 1] and [Document 3].", [True, False, True]),
    ("Documents 1 and 2 agree.", [True, True, False]),
    ("Documents 1, 2, and 3.", [True, True, True]),
    ("(Document 3)", [False, False, True]),
    ("No citation here.", [False, False, False]),
    ("Document 9 does not exist.", [False, False, False]),
])
def test_citation_formats(ask, fake_ollama, answer, expected):
    fake_ollama.answer = answer
    result = ask("waterproof", domain="products", n=3, method="hybrid")
    assert [s["cited"] for s in result["sources"]] == expected


def test_refusal_cites_nothing_even_if_it_mentions_a_document(ask, fake_ollama):
    fake_ollama.answer = "I don't have enough information. Document 1 is about shoes."
    result = ask("waterproof", domain="products", n=3, method="hybrid")
    assert result["sources"]
    assert not any(s["cited"] for s in result["sources"])


def test_chunks_beyond_the_prompt_are_never_cited(ask, fake_ollama):
    fake_ollama.answer = "Document 4 says so."  # only 3 chunks are in the prompt
    result = ask("waterproof", domain="products", n=5, method="hybrid")
    assert len(result["sources"]) == 5
    assert not any(s["cited"] for s in result["sources"])
