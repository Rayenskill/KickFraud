"""Cross-card aggregates + rolling per-card velocity windows.

All windows are SLIDING (relative), never date-keyed (see docs/CORRECTIONS.md):
    - (merchant, ~2h window) -> distinct cards charged >$200  (P4 cross-card burst)
    - per-card rolling velocity: small online txns in ~10-15 min  (P1 card-testing)
    - IP -> cards, device -> cards (shared-infra signals)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta


def build_aggregates(rows: list[dict]) -> dict:
    """Return cross-card maps + per-card rolling-window helpers.

    Returns dict with keys:
        merchant_bursts: {merchant: [{cards: set, timestamps: list, amounts: list, window_start, window_end}]}
        card_velocity: {card_id: [sorted list of (timestamp_dt, row) for small online txns]}
        ip_to_cards: {ip: set of card_ids}
        device_to_cards: {device: set of card_ids}
        card_txns_sorted: {card_id: [rows sorted by timestamp]}
    """
    # Parse timestamps once for sorting
    parsed_rows = []
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["timestamp"])
        except (ValueError, TypeError):
            dt = datetime.min
        parsed_rows.append((dt, row))
    parsed_rows.sort(key=lambda x: x[0])

    # IP -> cards and device -> cards
    ip_to_cards: dict[str, set[str]] = defaultdict(set)
    device_to_cards: dict[str, set[str]] = defaultdict(set)
    for _, row in parsed_rows:
        if row.get("ip_address"):
            ip_to_cards[row["ip_address"]].add(row["card_id"])
        if row.get("device_id"):
            device_to_cards[row["device_id"]].add(row["card_id"])

    # Per-card sorted transactions (for velocity and context)
    card_txns_sorted: dict[str, list[tuple[datetime, dict]]] = defaultdict(list)
    for dt, row in parsed_rows:
        card_txns_sorted[row["card_id"]].append((dt, row))

    # P1: per-card velocity — small (≤$15) online txns, sorted by time
    card_velocity: dict[str, list[tuple[datetime, dict]]] = defaultdict(list)
    for dt, row in parsed_rows:
        if row["channel"] == "online" and row["amount"] <= 15.0:
            card_velocity[row["card_id"]].append((dt, row))

    # P4: merchant burst windows — sliding 2h window per merchant, only >$200 txns
    # Group high-value txns per merchant
    merchant_high_value: dict[str, list[tuple[datetime, dict]]] = defaultdict(list)
    for dt, row in parsed_rows:
        if row["amount"] > 200.0:
            merchant_high_value[row["merchant"]].append((dt, row))

    # Build burst windows: for each merchant, find clusters of ≥5 distinct cards within 2h
    merchant_bursts: dict[str, list[dict]] = defaultdict(list)
    window_size = timedelta(hours=2)

    for merchant, txn_list in merchant_high_value.items():
        if len(txn_list) < 5:
            continue
        # Sliding window: for each txn as window start, find all within 2h
        for i, (start_dt, _) in enumerate(txn_list):
            window_end = start_dt + window_size
            window_cards: set[str] = set()
            window_txns: list[tuple[datetime, dict]] = []
            for j in range(i, len(txn_list)):
                t_dt, t_row = txn_list[j]
                if t_dt > window_end:
                    break
                window_cards.add(t_row["card_id"])
                window_txns.append((t_dt, t_row))

            if len(window_cards) >= 5:
                # Check if we already have a burst that overlaps heavily
                burst_key = frozenset(window_cards)
                already_exists = False
                for existing in merchant_bursts[merchant]:
                    if frozenset(existing["cards"]) == burst_key:
                        already_exists = True
                        break
                if not already_exists:
                    merchant_bursts[merchant].append({
                        "cards": window_cards,
                        "timestamps": [t[0] for t in window_txns],
                        "amounts": [t[1]["amount"] for t in window_txns],
                        "window_start": start_dt,
                        "window_end": window_txns[-1][0],
                        "txn_ids": [t[1]["transaction_id"] for t in window_txns],
                    })

    return {
        "merchant_bursts": dict(merchant_bursts),
        "card_velocity": dict(card_velocity),
        "ip_to_cards": dict(ip_to_cards),
        "device_to_cards": dict(device_to_cards),
        "card_txns_sorted": dict(card_txns_sorted),
    }
