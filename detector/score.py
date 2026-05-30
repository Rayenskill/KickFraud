"""Orchestrator: csv -> scored records + graph edges + transactions_flagged.csv.

Run once at API startup, or standalone:
    python -m detector.score data/transactions.csv
"""
from __future__ import annotations

import sys

# Default cost-aware cutoff over fixed 0..1 scores; POST /threshold moves this live.
DEFAULT_THRESHOLD = 0.42


def score_transactions(rows: list[dict]) -> list:
    """Build baselines + aggregates, run every signal per row, return ScoredRecords.

    TODO (step 1): baselines.build_card_baselines -> aggregates.build_aggregates ->
    for each row collect fired Reasons from signals.SIGNALS -> fraud_score = normalized
    sum of weights -> rank reasons by weight desc -> label vs DEFAULT_THRESHOLD.
    """
    raise NotImplementedError("detector.score.score_transactions — step 1")


def build_graph(records: list) -> dict:
    """Derive ring-graph nodes + edges (co_burst hubs, shared_ip, shared_device). TODO (step 1)."""
    raise NotImplementedError("detector.score.build_graph — step 1")


def relabel(records: list, threshold: float = DEFAULT_THRESHOLD) -> list:
    """Re-label in place against a cutoff over fixed scores (used by POST /threshold)."""
    for r in records:
        r.label = "fraud" if r.fraud_score >= threshold else "clear"
    return records


def main(argv: list[str]) -> int:
    from detector import io  # local import keeps module import cheap

    path = argv[0] if argv else "data/transactions.csv"
    rows = io.load_transactions(path)
    records = score_transactions(rows)
    io.write_flagged_csv(records, "transactions_flagged.csv")
    flagged = sum(1 for r in records if r.label == "fraud")
    print(f"scored {len(records)} rows, flagged {flagged} -> transactions_flagged.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
