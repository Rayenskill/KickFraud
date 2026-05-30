"""One function per signal + weight constants + reason strings.

Score model (docs/DETECTION.md): score(txn) = sum of fired signal weights, normalized to
0..1. Each fired signal emits a Reason(signal, weight, text). Weights are top-of-module
constants so tuning (H14-H18) is editing numbers in one file.

Validated rules (docs/CORRECTIONS.md — measured, ~0 FP unless noted; all relative/behavioral,
NEVER date-keyed):
    velocity_burst (P1)          >=4 small (<=$15) online txns in ~10-15 min
    merchant_burst_cross_card(P4) >=5 distinct cards / merchant / ~2h, each >$200
    atypical_category + country (P2) BOTH must fire; neither alone crosses threshold
    amount_vs_card_median (P3)   amount >= ~12x the card's median + high-risk category
"""
from __future__ import annotations

from detector.schema import Reason

# --- pattern weights (raw; normalized in score.py) ------------------------
W_MERCHANT_BURST_CROSS_CARD = 0.46   # P4
W_AMOUNT_VS_CARD_MEDIAN = 0.42       # P3
W_VELOCITY_BURST = 0.40              # P1
W_ATYPICAL_CATEGORY_FOR_CARD = 0.22  # P2 (only crosses combined with country)
W_ATYPICAL_COUNTRY_FOR_CARD = 0.22   # P2
W_HIGH_RISK_MERCHANT = 0.18          # P3 support
# --- defensive / cheap signals --------------------------------------------
W_SHARED_IP_ACROSS_CARDS = 0.10
W_SHARED_DEVICE_ACROSS_CARDS = 0.10
W_NEW_DEVICE_OR_IP_FOR_CARD = 0.08

# --- thresholds (relative / behavioral) -----------------------------------
P1_SMALL_AMOUNT = 15.0
P1_MIN_TXNS = 4
P1_WINDOW_MIN = 15
P4_MIN_CARDS = 5
P4_MIN_AMOUNT = 200.0
P4_WINDOW_MIN = 120
P3_MEDIAN_MULTIPLE = 12.0


def velocity_burst(row, baseline, agg) -> Reason | None:
    """P1 card-testing micro-burst. TODO (step 1)."""
    raise NotImplementedError("signals.velocity_burst — step 1")


def merchant_burst_cross_card(row, baseline, agg) -> Reason | None:
    """P4 coordinated processor attack. Keep the >$200 guard. TODO (step 1)."""
    raise NotImplementedError("signals.merchant_burst_cross_card — step 1")


def atypical_category_for_card(row, baseline, agg) -> Reason | None:
    """P2 part A. TODO (step 1)."""
    raise NotImplementedError("signals.atypical_category_for_card — step 1")


def atypical_country_for_card(row, baseline, agg) -> Reason | None:
    """P2 part B. Must combine with category to matter. TODO (step 1)."""
    raise NotImplementedError("signals.atypical_country_for_card — step 1")


def amount_vs_card_median(row, baseline, agg) -> Reason | None:
    """P3 bust-out outlier. TODO (step 1)."""
    raise NotImplementedError("signals.amount_vs_card_median — step 1")


def high_risk_merchant(row, baseline, agg) -> Reason | None:
    """P3 support: QuickPay Online / gift_card / electronics over threshold. TODO (step 1)."""
    raise NotImplementedError("signals.high_risk_merchant — step 1")


def shared_ip_across_cards(row, baseline, agg) -> Reason | None:
    """Defensive: this IP used by >1 card. TODO (step 1)."""
    raise NotImplementedError("signals.shared_ip_across_cards — step 1")


def shared_device_across_cards(row, baseline, agg) -> Reason | None:
    """Defensive: this device used by >1 card. TODO (step 1)."""
    raise NotImplementedError("signals.shared_device_across_cards — step 1")


def new_device_or_ip_for_card(row, baseline, agg) -> Reason | None:
    """Defensive: online txn on a device/IP new to the card. TODO (step 1)."""
    raise NotImplementedError("signals.new_device_or_ip_for_card — step 1")


# Registry the scorer iterates over (order is display-rank tiebreak only; reasons are
# re-sorted by weight in score.py).
SIGNALS = (
    merchant_burst_cross_card,
    amount_vs_card_median,
    velocity_burst,
    atypical_category_for_card,
    atypical_country_for_card,
    high_risk_merchant,
    shared_ip_across_cards,
    shared_device_across_cards,
    new_device_or_ip_for_card,
)
