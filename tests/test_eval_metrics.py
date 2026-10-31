"""Unit tests for the evaluation metrics (eval/metrics.py)."""
import math

import pytest

from eval import metrics as m


def test_mrr_uses_the_first_relevant_rank():
    assert m.mrr_at_k(["a", "b", "c"], {"c"}, 10) == pytest.approx(1 / 3)
    assert m.mrr_at_k(["a", "b", "c"], {"a", "c"}, 10) == 1.0
    assert m.mrr_at_k(["a", "b", "c"], {"z"}, 10) == 0.0


def test_mrr_ignores_relevant_items_below_the_cutoff():
    assert m.mrr_at_k(["a", "b", "c"], {"c"}, 2) == 0.0


def test_span_recall_counts_covered_spans():
    spans = [{"x1", "x2"}, {"y1"}, {"z1"}]
    assert m.span_recall_at_k(["x2", "q", "y1"], spans, 3) == pytest.approx(2 / 3)
    assert m.span_recall_at_k(["x2", "q", "y1"], spans, 1) == pytest.approx(1 / 3)
    assert m.span_recall_at_k([], spans, 5) == 0.0


def test_span_recall_requires_spans():
    with pytest.raises(ValueError):
        m.span_recall_at_k(["a"], [], 3)


def test_precision_divides_by_k_even_with_short_results():
    assert m.precision_at_k(["a", "b"], {"a", "b"}, 5) == pytest.approx(2 / 5)
    assert m.precision_at_k(["a", "x", "b"], {"a", "b"}, 3) == pytest.approx(2 / 3)


def test_capped_recall_is_one_for_a_perfect_top_k_even_with_many_gold_rows():
    gold = {str(i) for i in range(266)}
    assert m.capped_recall_at_k([str(i) for i in range(10)], gold, 10) == 1.0
    assert m.capped_recall_at_k(["0", "x", "y"], gold, 3) == pytest.approx(1 / 3)
    # fewer gold rows than k: all of them must be found
    assert m.capped_recall_at_k(["a", "x", "b"], {"a", "b", "c", "d"}, 10) == pytest.approx(2 / 4)


def test_hit_at_k():
    assert m.hit_at_k(["a", "b"], {"b"}, 1) == 0.0
    assert m.hit_at_k(["a", "b"], {"b"}, 2) == 1.0


def test_metric_bundles_have_the_documented_keys():
    ev = m.evidence_metrics(["a"], [{"a"}])
    assert set(ev) == {"span_recall@1", "span_recall@3", "span_recall@5", "span_recall@10", "mrr@10", "mrr@3"}
    st = m.set_metrics(["a"], {"a"})
    assert "precision@5" in st and "capped_recall@10" in st and "hit@1" in st and "mrr@10" in st


def test_percentile_and_mean():
    values = [1.0, 2.0, 3.0, 4.0, 100.0]
    assert m.mean(values) == pytest.approx(22.0)
    assert m.percentile(values, 50) == 3.0
    assert m.percentile(values, 95) == 100.0
    assert math.isnan(m.mean([]))
