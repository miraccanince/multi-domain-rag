"""
Retrieval metrics. Pure functions over ranked lists of identifiers, no I/O.

Two kinds of question are scored differently:

  * Evidence questions (documents): the gold evidence is a list of spans, each
    represented by the set of chunk keys that contain it. The question is
    answered well when the retrieved chunks cover the spans.
        span_recall_at_k : share of gold spans covered by at least one of the top k chunks
        mrr_at_k         : 1 / rank of the first chunk that covers any gold span

  * Set questions (vehicles): the gold evidence is the set of all rows that satisfy
    a rule, which can be large (266 rows for "battery-electric vehicles").
        precision_at_k       : share of the top k results that are gold rows
        capped_recall_at_k   : gold rows found / min(number of gold rows, k), so a
                               perfect top k scores 1.0 even when there are more
                               than k gold rows
        hit_at_k             : 1 if any gold row is in the top k
        mrr_at_k             : 1 / rank of the first gold row
"""

from typing import Dict, Iterable, List, Sequence, Set

KS = (1, 3, 5, 10)


def first_rank(ranked: Sequence[str], relevant: Set[str], k: int) -> int:
    """1-based rank of the first relevant item within the top k, or 0 if none."""
    for position, item in enumerate(ranked[:k], 1):
        if item in relevant:
            return position
    return 0


def mrr_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    rank = first_rank(ranked, relevant, k)
    return 1.0 / rank if rank else 0.0


def span_recall_at_k(ranked: Sequence[str], spans: List[Set[str]], k: int) -> float:
    if not spans:
        raise ValueError("a question with gold spans must have at least one span")
    top = set(ranked[:k])
    return sum(1 for keys in spans if keys & top) / len(spans)


def precision_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / k


def capped_recall_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        raise ValueError("no gold rows")
    return len(set(ranked[:k]) & relevant) / min(len(relevant), k)


def hit_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    return 1.0 if first_rank(ranked, relevant, k) else 0.0


def evidence_metrics(ranked: Sequence[str], spans: List[Set[str]], ks: Iterable[int] = KS) -> Dict[str, float]:
    union = set().union(*spans)
    result = {f"span_recall@{k}": span_recall_at_k(ranked, spans, k) for k in ks}
    result["mrr@10"] = mrr_at_k(ranked, union, 10)
    result["mrr@3"] = mrr_at_k(ranked, union, 3)
    return result


def set_metrics(ranked: Sequence[str], relevant: Set[str], ks: Iterable[int] = KS) -> Dict[str, float]:
    result = {}
    for k in ks:
        result[f"precision@{k}"] = precision_at_k(ranked, relevant, k)
        result[f"capped_recall@{k}"] = capped_recall_at_k(ranked, relevant, k)
        result[f"hit@{k}"] = hit_at_k(ranked, relevant, k)
    result["mrr@10"] = mrr_at_k(ranked, relevant, 10)
    result["mrr@3"] = mrr_at_k(ranked, relevant, 3)
    return result


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile, q in [0, 100]."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(q / 100 * len(ordered) + 0.5)) - 1))
    return ordered[index]
