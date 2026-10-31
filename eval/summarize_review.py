"""
Combine a filled-in review sheet with its key and report mean scores per configuration.

    python -m eval.summarize_review eval/results/review_<time>.csv eval/results/review_key_<time>.json

Scoring rubric (see eval/README.md): correctness and attribution are 0, 1 or 2.
Leave attribution empty when it does not apply (for example a correct refusal).
"""

import collections
import csv
import json
import sys

from eval import metrics


def main(sheet_path: str, key_path: str) -> None:
    key = json.load(open(key_path))
    scores = collections.defaultdict(lambda: {"correctness": [], "attribution": []})
    blanks = 0
    for row in csv.DictReader(open(sheet_path, encoding="utf-8")):
        info = key[row["item"]]
        for field, name in (("correctness_0_1_2", "correctness"), ("attribution_0_1_2", "attribution")):
            value = row[field].strip()
            if value == "":
                blanks += 1 if name == "correctness" else 0
                continue
            if value not in ("0", "1", "2"):
                sys.exit(f"item {row['item']}: {field} must be 0, 1 or 2, got '{value}'")
            for group in (info["config"], f"{info['config']} / {info['category']}"):
                scores[group][name].append(int(value))
    if blanks:
        print(f"WARNING: {blanks} items have no correctness score yet")
    for group in sorted(scores):
        c, a = scores[group]["correctness"], scores[group]["attribution"]
        print(f"{group:40s} correctness mean={metrics.mean(c):.2f} (n={len(c)})   "
              f"attribution mean={metrics.mean(a):.2f} (n={len(a)})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
