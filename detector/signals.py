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

from datetime import datetime, timedelta

from detector.schema import Reason

# --- pattern weights (raw; normalized in score.py) ------------------------
W_MERCHANT_BURST_CROSS_CARD = 0.46   # P4
W_AMOUNT_VS_CARD_MEDIAN = 0.45       # P3
W_VELOCITY_BURST = 0.45              # P1
W_ATYPICAL_CATEGORY_FOR_CARD = 0.16  # P2 (only crosses combined with country + something else)
W_ATYPICAL_COUNTRY_FOR_CARD = 0.16   # P2
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

# High-risk merchants/categories for P3 support
HIGH_RISK_MERCHANTS = {"QuickPay Online"}
HIGH_RISK_CATEGORIES = {"gift_card", "electronics"}
HIGH_RISK_CATEGORY_AMOUNT = 250.0


def velocity_burst(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P1 card-testing micro-burst: >=4 small (<=15) online txns in ~10-15 min."""
    card_id = row["card_id"]
    velocity_txns = agg.get("card_velocity", {}).get(card_id, [])
    if len(velocity_txns) < P1_MIN_TXNS:
        return None

    # Check if this row is part of a velocity burst
    try:
        row_dt = datetime.fromisoformat(row["timestamp"])
    except (ValueError, TypeError):
        return None

    # Only fire if this row is itself a small online txn in a burst
    if row["channel"] != "online" or row["amount"] > P1_SMALL_AMOUNT:
        return None

    window = timedelta(minutes=P1_WINDOW_MIN)
    # Find the best window containing this txn
    best_count = 0
    best_window_min = 0
    for i, (dt_i, _) in enumerate(velocity_txns):
        if dt_i > row_dt:
            break
        count = 0
        last_dt = dt_i
        for j in range(i, len(velocity_txns)):
            dt_j, _ = velocity_txns[j]
            if dt_j - dt_i > window:
                break
            count += 1
            last_dt = dt_j
        # Check if this row is in this window
        if dt_i <= row_dt <= dt_i + window and count >= P1_MIN_TXNS:
            if count > best_count:
                best_count = count
                best_window_min = int((last_dt - dt_i).total_seconds() / 60)

    if best_count >= P1_MIN_TXNS:
        return Reason(
            signal="velocity_burst",
            weight=W_VELOCITY_BURST,
            text=f"{best_count} small online txns in {best_window_min} min",
        )
    return None


def merchant_burst_cross_card(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P4 coordinated processor attack. Keep the >$200 guard."""
    if row["amount"] <= P4_MIN_AMOUNT:
        return None

    merchant = row["merchant"]
    bursts = agg.get("merchant_bursts", {}).get(merchant, [])
    if not bursts:
        return None

    # Check if this transaction is part of any burst
    row_id = row["transaction_id"]
    for burst in bursts:
        if row_id in burst.get("txn_ids", []):
            n_cards = len(burst["cards"])
            window_start = burst["window_start"]
            window_end = burst["window_end"]
            window_min = int((window_end - window_start).total_seconds() / 60)
            return Reason(
                signal="merchant_burst_cross_card",
                weight=W_MERCHANT_BURST_CROSS_CARD,
                text=f"'{merchant}' hit by {n_cards} cards >${int(P4_MIN_AMOUNT)} in {window_min} min",
            )

    # Also check by timestamp proximity even if txn_id not directly in burst
    try:
        row_dt = datetime.fromisoformat(row["timestamp"])
    except (ValueError, TypeError):
        return None

    for burst in bursts:
        if burst["window_start"] <= row_dt <= burst["window_end"]:
            if row["card_id"] in burst["cards"]:
                n_cards = len(burst["cards"])
                window_min = int((burst["window_end"] - burst["window_start"]).total_seconds() / 60)
                return Reason(
                    signal="merchant_burst_cross_card",
                    weight=W_MERCHANT_BURST_CROSS_CARD,
                    text=f"'{merchant}' hit by {n_cards} cards >${int(P4_MIN_AMOUNT)} in {window_min} min",
                )
    return None


def atypical_category_for_card(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P2 part A: category not in card's history prior to this transaction."""
    try:
        row_dt = datetime.fromisoformat(row["timestamp"])
    except:
        return None
        
    history = agg.get("card_txns_sorted", {}).get(row["card_id"], [])
    categories = set()
    for dt, r in history:
        if dt < row_dt:
            categories.add(r["category"])
            
    cat = row["category"]
    if cat not in categories and len(categories) > 0:
        return Reason(
            signal="atypical_category_for_card",
            weight=W_ATYPICAL_CATEGORY_FOR_CARD,
            text=f"{cat} never seen on this card",
        )
    return None


def atypical_country_for_card(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P2 part B: merchant_country not in card's history prior to this txn."""
    try:
        row_dt = datetime.fromisoformat(row["timestamp"])
    except:
        return None
        
    history = agg.get("card_txns_sorted", {}).get(row["card_id"], [])
    countries = set()
    for dt, r in history:
        if dt < row_dt:
            countries.add(r["merchant_country"])
            
    country = row["merchant_country"]
    if country not in countries and len(countries) > 0:
        return Reason(
            signal="atypical_country_for_card",
            weight=W_ATYPICAL_COUNTRY_FOR_CARD,
            text=f"first {country} purchase for this card",
        )
    return None


def amount_vs_card_median(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P3 bust-out outlier: amount >= P3_MEDIAN_MULTIPLE × card median."""
    if not baseline:
        return None
    med = baseline.get("amount_median", 0)
    if med <= 0:
        return None
    multiple = row["amount"] / med
    if multiple >= P3_MEDIAN_MULTIPLE:
        return Reason(
            signal="amount_vs_card_median",
            weight=W_AMOUNT_VS_CARD_MEDIAN,
            text=f"${row['amount']:.0f} is {multiple:.0f}× this card's median",
        )
    return None


def high_risk_merchant(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """P3 support: QuickPay Online / gift_card / electronics over threshold."""
    merchant = row["merchant"]
    category = row["category"]
    amount = row["amount"]

    if merchant in HIGH_RISK_MERCHANTS:
        return Reason(
            signal="high_risk_merchant",
            weight=W_HIGH_RISK_MERCHANT,
            text=f"high-risk merchant '{merchant}'",
        )
    if category in HIGH_RISK_CATEGORIES and amount > HIGH_RISK_CATEGORY_AMOUNT:
        return Reason(
            signal="high_risk_merchant",
            weight=W_HIGH_RISK_MERCHANT,
            text=f"high-risk category over ${int(HIGH_RISK_CATEGORY_AMOUNT)}",
        )
    return None


def shared_ip_across_cards(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """Defensive: this IP used by >1 card."""
    ip = row.get("ip_address")
    if not ip:
        return None
    ip_cards = agg.get("ip_to_cards", {}).get(ip, set())
    other_cards = ip_cards - {row["card_id"]}
    if other_cards:
        other = sorted(other_cards)[0]
        return Reason(
            signal="shared_ip_across_cards",
            weight=W_SHARED_IP_ACROSS_CARDS,
            text=f"IP shared with {other}",
        )
    return None


def shared_device_across_cards(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """Defensive: this device used by >1 card."""
    dev = row.get("device_id")
    if not dev:
        return None
    dev_cards = agg.get("device_to_cards", {}).get(dev, set())
    other_cards = dev_cards - {row["card_id"]}
    if other_cards:
        other = sorted(other_cards)[0]
        return Reason(
            signal="shared_device_across_cards",
            weight=W_SHARED_DEVICE_ACROSS_CARDS,
            text=f"device shared with {other}",
        )
    return None


def new_device_or_ip_for_card(row: dict, baseline: dict, agg: dict) -> Reason | None:
    """Defensive: online txn on a device/IP new to the card (prior to this txn)."""
    if row["channel"] != "online":
        return None
        
    try:
        row_dt = datetime.fromisoformat(row["timestamp"])
    except:
        return None
        
    history = agg.get("card_txns_sorted", {}).get(row["card_id"], [])
    devices = set()
    ips = set()
    for dt, r in history:
        if dt < row_dt:
            if r.get("device_id"): devices.add(r["device_id"])
            if r.get("ip_address"): ips.add(r["ip_address"])

    new_parts = []
    dev = row.get("device_id")
    ip = row.get("ip_address")

    if dev and dev not in devices and len(devices) > 0:
        new_parts.append("device")
    if ip and ip not in ips and len(ips) > 0:
        new_parts.append("IP")

    if new_parts:
        return Reason(
            signal="new_device_or_ip_for_card",
            weight=W_NEW_DEVICE_OR_IP_FOR_CARD,
            text=f"new {' + '.join(new_parts)} for this card",
        )
    return None


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
