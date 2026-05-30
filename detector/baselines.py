"""Per-card behavioral baselines (NO fixed dates — see docs/CORRECTIONS.md).

For each card: median/MAD amount, typical categories, typical merchant_country,
channel mix, known devices/IPs, hour-of-day profile.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median


def _mad(values: list[float], med: float) -> float:
    """Median absolute deviation — robust to outliers."""
    if not values:
        return 0.0
    return median(abs(v - med) for v in values)


def build_card_baselines(rows: list[dict]) -> dict:
    """Return {card_id: baseline dict} computed in one pass.

    Baseline keys:
        amount_median, amount_mad,
        categories (set), countries (set), channels (set),
        devices (set), ips (set),
        hours (list[int]) — raw hours for hour-of-day profiling,
        txn_count
    """
    # Group rows by card
    by_card: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_card[row["card_id"]].append(row)

    baselines: dict[str, dict] = {}
    for card_id, txns in by_card.items():
        amounts = [t["amount"] for t in txns]
        med = median(amounts) if amounts else 0.0
        mad = _mad(amounts, med)

        categories: set[str] = set()
        countries: set[str] = set()
        channels: set[str] = set()
        devices: set[str] = set()
        ips: set[str] = set()
        hours: list[int] = []

        for t in txns:
            categories.add(t["category"])
            countries.add(t["merchant_country"])
            channels.add(t["channel"])
            if t.get("device_id"):
                devices.add(t["device_id"])
            if t.get("ip_address"):
                ips.add(t["ip_address"])
            try:
                dt = datetime.fromisoformat(t["timestamp"])
                hours.append(dt.hour)
            except (ValueError, TypeError):
                pass

        baselines[card_id] = {
            "amount_median": med,
            "amount_mad": mad,
            "categories": categories,
            "countries": countries,
            "channels": channels,
            "devices": devices,
            "ips": ips,
            "hours": hours,
            "txn_count": len(txns),
        }

    return baselines
