"""Cross-card aggregates + rolling per-card velocity windows.

All windows are SLIDING (relative), never date-keyed (see docs/CORRECTIONS.md):
    - (merchant, ~2h window) -> distinct cards charged >$200  (P4 cross-card burst)
    - per-card rolling velocity: small online txns in ~10-15 min  (P1 card-testing)
    - IP -> cards, device -> cards (shared-infra signals)
"""
from __future__ import annotations


def build_aggregates(rows: list[dict]) -> dict:
    """Return cross-card maps + per-card rolling-window helpers.

    TODO (step 1): merchant burst windows, per-card velocity windows, ip/device maps.
    """
    raise NotImplementedError("detector.aggregates.build_aggregates — step 1")
