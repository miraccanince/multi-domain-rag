"""
Ground truth for the evaluation: loading questions, checking gold spans and rows,
and mapping gold evidence to the chunks and rows that the application indexes.

Gold evidence is stored in a form that does not depend on chunking:
  * documents: a PDF name, a 1-based PDF page and a verbatim text span
  * vehicles:  a rule over EPA columns, plus the resulting EPA `id` values
"""

import csv
import json
import re
from typing import Dict, List

from eval import sources

QUESTIONS_FILE = sources.EVAL_DIR / "questions.jsonl"


def normalize(text: str) -> str:
    """Collapse all whitespace so line breaks and page layout do not matter."""
    return re.sub(r"\s+", " ", text).strip()


def load_questions(split: str = "all") -> List[dict]:
    questions = [json.loads(line) for line in QUESTIONS_FILE.read_text().splitlines() if line.strip()]
    if split != "all":
        questions = [q for q in questions if q["split"] == split]
    return questions


# ---- vehicles -------------------------------------------------------------

def load_vehicle_rows() -> List[Dict[str, str]]:
    """The EPA snapshot, in file order. The position in this list is the row_id the CSV loader assigns."""
    with open(sources.EPA_SNAPSHOT, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _number(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return float("nan")


def row_matches(row: Dict[str, str], conditions: List[list]) -> bool:
    for column, op, value in conditions:
        cell = row[column]
        if op == "==":
            ok = cell == value
        elif op == "!=":
            ok = cell != value
        elif op == "startswith":
            ok = cell.startswith(value)
        elif op == "not_startswith":
            ok = not cell.startswith(value)
        elif op == "contains":
            ok = value in cell
        elif op == "<":
            ok = _number(cell) < float(value)
        elif op == ">":
            ok = _number(cell) > float(value)
        else:
            raise ValueError(f"unknown operator {op}")
        if not ok:
            return False
    return True


def rows_for_rule(rows: List[Dict[str, str]], conditions: List[list]) -> List[Dict[str, str]]:
    return [r for r in rows if row_matches(r, conditions)]


def aggregate(rows: List[Dict[str, str]], spec: dict):
    """Exact answer for a structured question: count, argmax or mean over the matching rows."""
    if spec["op"] == "count":
        return len(rows)
    if spec["op"] == "mean":
        values = [_number(r[spec["column"]]) for r in rows]
        return round(sum(values) / len(values), 2)
    if spec["op"] == "argmax":
        best = max(rows, key=lambda r: _number(r[spec["column"]]))
        return f"{best['make']} {best['model']} ({spec['column']}={best[spec['column']]})"
    raise ValueError(f"unknown aggregate {spec['op']}")


# ---- documents ------------------------------------------------------------

def span_offsets(page_text: str, span: str):
    """(start, end) of a gold span in the normalized page text, or None if it is not there."""
    page, target = normalize(page_text), normalize(span)
    start = page.find(target)
    return None if start < 0 else (start, start + len(target))


def chunk_offsets(page_text: str, chunk_text: str):
    page, chunk = normalize(page_text), normalize(chunk_text)
    start = page.find(chunk)
    return None if start < 0 else (start, start + len(chunk))


def covers_span(chunk_range, span_range, minimum_fraction: float = 0.5) -> bool:
    """A chunk counts as evidence when it contains at least half of the gold span."""
    overlap = min(chunk_range[1], span_range[1]) - max(chunk_range[0], span_range[0])
    return overlap >= minimum_fraction * (span_range[1] - span_range[0])


# ---- mapping gold evidence to what the application indexes -----------------

def pdf_stem(source: str) -> str:
    return source.rsplit("/", 1)[-1].removesuffix(".pdf")


def chunk_key(source: str, page_index: int, text: str) -> str:
    """Identify a chunk by file, 0-based page and text, independent of the random IDs ChromaDB assigns."""
    import hashlib
    return f"{pdf_stem(source)}|{page_index}|{hashlib.sha1(normalize(text).encode()).hexdigest()[:12]}"


def load_page_texts() -> Dict[tuple, str]:
    """(pdf stem, 0-based page) -> page text as the application's PDF loader returns it."""
    from langchain_community.document_loaders import PyPDFLoader
    pages = {}
    for name in sources.NIST_FILES:
        for document in PyPDFLoader(str(sources.NIST_DIR / name)).load():
            pages[(pdf_stem(name), document.metadata["page"])] = document.page_content
    return pages


def load_pdf_chunks():
    """The chunks the application's ingestion produces for the NIST PDFs (baseline representation)."""
    from rag.ingestion.pdf_loader import load_pdfs_from_directory
    return load_pdfs_from_directory(str(sources.NIST_DIR), domain="technical")


def gold_chunk_keys(question: dict, chunks, pages) -> List[set]:
    """
    For each gold span of a document question, the set of chunk keys that contain
    at least half of the span. One set per span, so multi-span questions can be
    scored by how many spans are covered.
    """
    result = []
    for span in question["gold_spans"]:
        page_index = span["page"] - 1
        page_text = pages[(span["doc"], page_index)]
        span_range = span_offsets(page_text, span["text"])
        keys = set()
        if span_range:
            for chunk in chunks:
                if pdf_stem(chunk.metadata["source"]) != span["doc"] or chunk.metadata["page"] != page_index:
                    continue
                chunk_range = chunk_offsets(page_text, chunk.page_content)
                if chunk_range and covers_span(chunk_range, span_range):
                    keys.add(chunk_key(chunk.metadata["source"], page_index, chunk.page_content))
        result.append(keys)
    return result
