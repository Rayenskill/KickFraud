"""Per-card behavioral baselines (NO fixed dates — see docs/CORRECTIONS.md).

For each card: median/MAD amount, typical categories, typical merchant_country,
channel mix, known devices/IPs, hour-of-day profile.
"""
from __future__ import annotations


def build_card_baselines(rows: list[dict]) -> dict:
    """Return {card_id: CardBaseline-like dict} computed in one pass.

    TODO (step 1): median + MAD of amount, category set, country set, channel mix,
    device/IP sets, hour histogram.
    """
    raise NotImplementedError("detector.baselines.build_card_baselines — step 1")
