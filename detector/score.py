"""Orchestrator: csv -> scored records + graph edges + transactions_flagged.csv.

Run once at API startup, or standalone:
    python -m detector.score data/transactions.csv
"""
from __future__ import annotations

import sys
from collections import defaultdict

from detector.aggregates import build_aggregates
from detector.baselines import build_card_baselines
from detector.schema import GraphEdge, GraphNode, Reason, ScoredRecord
from detector.signals import SIGNALS

# Default cost-aware cutoff over fixed 0..1 scores; POST /threshold moves this live.
DEFAULT_THRESHOLD = 0.42

# Maximum possible raw score (sum of all weights) — used for normalization.
_MAX_RAW_SCORE = sum(
    getattr(__import__("detector.signals", fromlist=[""]), w)
    for w in dir(__import__("detector.signals", fromlist=[""]))
    if w.startswith("W_")
)


def _compute_max_raw() -> float:
    """Compute the sum of all W_ weight constants in signals.py."""
    import detector.signals as sig
    total = 0.0
    for name in dir(sig):
        if name.startswith("W_"):
            total += getattr(sig, name)
    return total


def score_row(
    row: dict,
    baselines: dict,
    agg: dict,
    threshold: float = DEFAULT_THRESHOLD,
) -> ScoredRecord:
    """Score a single transaction against pre-built baselines + aggregates.

    Extracted from score_transactions so the live-ingestion pipeline
    (api/ingest.py) can score one new transaction without re-scoring the batch.

    Steps: run every signal -> sum fired weights (clamped to 1.0) -> rank reasons
    by weight desc -> label vs threshold.
    """
    card_id = row["card_id"]
    baseline = baselines.get(card_id, {})

    fired: list[Reason] = []
    for signal_fn in SIGNALS:
        result = signal_fn(row, baseline, agg)
        if result is not None:
            fired.append(result)

    raw_score = sum(r.weight for r in fired)
    fraud_score = min(raw_score, 1.0)
    fired.sort(key=lambda r: r.weight, reverse=True)
    label = "fraud" if fraud_score >= threshold else "clear"

    record = ScoredRecord(
        transaction_id=row["transaction_id"],
        card_id=card_id,
        timestamp=row["timestamp"],
        amount=row["amount"],
        merchant=row["merchant"],
        merchant_country=row["merchant_country"],
        category=row["category"],
        channel=row["channel"],
        card_median=baseline.get("amount_median", 0.0),
        device_id=row.get("device_id"),
        ip_address=row.get("ip_address"),
        fraud_score=round(fraud_score, 4),
        label=label,
        reasons=fired,
        review_status="pending",
    )
    # Stash cardholder_country for CSV export
    record.cardholder_country = row.get("cardholder_country", "")  # type: ignore[attr-defined]
    return record


def score_transactions(rows: list[dict]) -> list[ScoredRecord]:
    """Build baselines + aggregates, run every signal per row, return ScoredRecords.

    Pipeline:
    1. baselines.build_card_baselines -> per-card profiles
    2. aggregates.build_aggregates -> cross-card maps
    3. score_row() per transaction (fired reasons, summed weight, label vs threshold)
    """
    baselines = build_card_baselines(rows)
    agg = build_aggregates(rows)
    return [score_row(row, baselines, agg) for row in rows]


def _rfield(r, name: str):
    """Read a field from a ScoredRecord OR its dict form (the Mongo cache holds dicts)."""
    return r.get(name) if isinstance(r, dict) else getattr(r, name)


def build_graph(records: list, rows: list[dict]) -> dict:
    """Derive ring-graph nodes + edges (co_burst hubs, shared_ip, shared_device, and all transactions).

    `records` may be ScoredRecord instances (batch path) or dicts (Mongo cache path).
    Returns {nodes: [GraphNode.to_dict()], edges: [GraphEdge.to_dict()]}.
    """
    agg = build_aggregates(rows)

    nodes_map: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    seen_edges: set[tuple] = set()

    # Count flags per card
    card_flags: dict[str, int] = defaultdict(int)
    for r in records:
        if _rfield(r, "label") == "fraud":
            card_flags[_rfield(r, "card_id")] += 1

    # Add all basic transactions to build the full web
    for r in records:
        merchant = _rfield(r, "merchant")
        card_id = _rfield(r, "card_id")
        if merchant not in nodes_map:
            nodes_map[merchant] = GraphNode(id=merchant, type="merchant", flag_count=0)
        if card_id not in nodes_map:
            nodes_map[card_id] = GraphNode(id=card_id, type="card", flag_count=card_flags.get(card_id, 0))

        edge_key = (card_id, merchant, "transaction")
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append(GraphEdge(
                source=card_id,
                target=merchant,
                type="transaction",
                weight=1
            ))

    # Co-burst edges from merchant bursts
    merchant_bursts = agg.get("merchant_bursts", {})
    for merchant, bursts in merchant_bursts.items():
        if merchant in nodes_map:
            nodes_map[merchant].suspicious = True
        for burst in bursts:
            for card_id in burst["cards"]:
                edge_key = (card_id, merchant, "co_burst")
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(GraphEdge(
                        source=card_id,
                        target=merchant,
                        type="co_burst",
                        weight=len(burst["cards"]),
                    ))

    # Shared IP edges
    ip_to_cards = agg.get("ip_to_cards", {})
    for ip, cards in ip_to_cards.items():
        if len(cards) < 2:
            continue
        card_list = sorted(cards)
        for i in range(len(card_list)):
            for j in range(i + 1, len(card_list)):
                edge_key = (card_list[i], card_list[j], "shared_ip")
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    # Add card nodes
                    for cid in (card_list[i], card_list[j]):
                        if cid not in nodes_map:
                            nodes_map[cid] = GraphNode(
                                id=cid,
                                type="card",
                                flag_count=card_flags.get(cid, 0),
                            )
                    edges.append(GraphEdge(
                        source=card_list[i],
                        target=card_list[j],
                        type="shared_ip",
                        ip=ip,
                    ))

    # Shared device edges
    dev_to_cards = agg.get("device_to_cards", {})
    for dev, cards in dev_to_cards.items():
        if len(cards) < 2:
            continue
        card_list = sorted(cards)
        for i in range(len(card_list)):
            for j in range(i + 1, len(card_list)):
                edge_key = (card_list[i], card_list[j], "shared_device")
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    for cid in (card_list[i], card_list[j]):
                        if cid not in nodes_map:
                            nodes_map[cid] = GraphNode(
                                id=cid,
                                type="card",
                                flag_count=card_flags.get(cid, 0),
                            )
                    edges.append(GraphEdge(
                        source=card_list[i],
                        target=card_list[j],
                        type="shared_device",
                    ))

    return {
        "nodes": [n.to_dict() for n in nodes_map.values()],
        "edges": [e.to_dict() for e in edges],
    }


def relabel(records: list[ScoredRecord], threshold: float = DEFAULT_THRESHOLD) -> list[ScoredRecord]:
    """Re-label in place against a cutoff over fixed scores (used by POST /threshold)."""
    for r in records:
        r.label = "fraud" if r.fraud_score >= threshold else "clear"
    return records


def main(argv: list[str]) -> int:
    from detector import io  # local import keeps module import cheap

    path = argv[0] if argv else "data/transactions.csv"
    rows = io.load_transactions(path)
    records = score_transactions(rows)
    graph = build_graph(records, rows)
    io.write_flagged_csv(records, "transactions_flagged.csv")
    flagged = sum(1 for r in records if r.label == "fraud")
    print(f"scored {len(records)} rows, flagged {flagged} -> transactions_flagged.csv")
    print(f"graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
