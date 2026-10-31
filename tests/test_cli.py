"""
scripts.chat_cli driven with scripted keyboard input.

MOCKED: embeddings, Ollama and the interactive environment checks. REAL: the
ChromaDB collection, retrieval and the CLI's printing of answers and sources.
"""
import pytest

from rag import config
from rag.caching.cache_manager import get_query_cache
from scripts import chat_cli


@pytest.fixture
def cli(example_index, fake_ollama, monkeypatch):
    client, collection, _ = example_index
    get_query_cache().clear()  # module-level exact-match cache would hide LLM calls
    monkeypatch.setattr(config, "CHROMA_DIR", client.get_settings().persist_directory)
    monkeypatch.setattr(chat_cli, "check_ollama_running", lambda: True)
    monkeypatch.setattr(chat_cli, "warm_up_model", lambda **kw: True)
    monkeypatch.setattr(chat_cli, "check_indexing_needed", lambda c: False)
    monkeypatch.setattr(chat_cli, "select_domain", lambda domains: "automotive")
    # ask_question keeps a module-level engine; make sure this test builds its own
    monkeypatch.delattr(chat_cli.ask_question, "_hybrid_engine", raising=False)

    def run(*lines):
        inputs = iter(lines)
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
        chat_cli.main()

    run.ollama = fake_ollama
    return run


def test_question_prints_answer_and_page_source(cli, capsys):
    cli("What is a CAN error frame?", "/quit")
    out = capsys.readouterr().out
    assert "Answer:" in out
    assert cli.ollama.answer in out
    assert "vehicle_diagnostics.pdf (Page 1)" in out
    assert "Also retrieved, not cited" in out  # the fake answer cites Document 1 only
    assert "Goodbye!" in out


def test_domain_choice_limits_sources_to_that_domain(cli, capsys):
    cli("waterproof boots", "/quit")
    out = capsys.readouterr().out
    assert "catalog.csv" not in out
    assert "vehicle_diagnostics.pdf" in out


def test_commands_do_not_reach_the_llm(cli, capsys):
    cli("/stats", "/help", "/quit")
    out = capsys.readouterr().out
    assert "Total documents" in out
    assert cli.ollama.prompts == []


def test_ollama_failure_is_reported_not_raised(cli, capsys):
    cli.ollama.down = True
    cli("What is a CAN error frame?", "/quit")
    out = capsys.readouterr().out
    assert "[LLM error]" in out
    assert "Goodbye!" in out


def test_cli_never_kills_processes():
    """The CLI may only manage processes it started itself."""
    from pathlib import Path
    import re
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for folder in ("rag", "api", "scripts", "frontend"):
        for path in (root / folder).rglob("*.py"):
            if re.search(r"pkill|kill -9|\"kill\"|lsof|os\.kill", path.read_text()):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
