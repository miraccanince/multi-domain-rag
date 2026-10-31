"""
Protect the held-out questions.

Retrieval settings may be tuned on the dev split only. The test split is meant to be
run once per frozen configuration. Each test run is logged, and a second one needs an
explicit flag, so a repeated run is a conscious choice that shows up in the log.
"""

import datetime
import sys

from eval import sources

LEDGER = sources.RESULTS_DIR / "test_runs.log"


def check_split(split: str, final: bool, allow_rerun: bool, purpose: str, git_commit: str) -> None:
    if split == "dev":
        return
    if not final:
        sys.exit(f"The '{split}' split includes the held-out test questions. Re-run with --final "
                 "once the configuration is frozen, or use --split dev while developing.")
    previous = LEDGER.read_text().splitlines() if LEDGER.exists() else []
    same = [line for line in previous if f"purpose={purpose}" in line]
    if same and not allow_rerun:
        sys.exit(f"The test split was already run for '{purpose}':\n  " + "\n  ".join(same)
                 + "\nUse --allow-rerun to run it again (the new run is logged as well).")
    sources.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        f.write(f"{stamp} split={split} purpose={purpose} commit={git_commit}\n")
