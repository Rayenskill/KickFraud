"""Live-ingestion pipeline: a new transaction -> score -> decision tree -> maybe alert.

This is the "when a new transaction is added to the database, run it through the decision
tree and decide whether to notify the fraud analyst" path. The functions here are
state-light: they build a scored record and a routing decision from the *current* set of
rows. `api/main.py` owns the mutable app caches (RAW_ROWS / RECORDS / GRAPH) and the
persistence/notification side effects, so ownership of state stays in one place.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from detector import decision_tree
from detector.aggregates import build_aggregates
from detector.baselines import build_card_baselines
from detector.schema import ScoredRecord
from detector.score import score_row

REQUIRED = ("card_id", "amount", "merchant", "category", "channel", "merchant_country")


def normalize_row(body: dict, existing_ids: set[str] | None = None) -> dict:
    """Turn an inbound JSON body into a detector row dict (same shape as detector.io).

    Raises ValueError if a required field is missing. Auto-assigns a transaction_id and a
    timestamp when absent, matching the no-timezone ISO format used in the dataset.
    """
    missing = [f for f in REQUIRED if body.get(f) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")

    tid = (body.get("transaction_id") or "").strip()
    if not tid or (existing_ids and tid in existing_ids):
        tid = f"tx_live_{uuid.uuid4().hex[:8]}"

    timestamp = (body.get("timestamp") or "").strip()
    if not timestamp:
        timestamp = datetime.now().replace(microsecond=0).isoformat()

    return {
        "transaction_id": tid,
        "timestamp": timestamp,
        "card_id": str(body["card_id"]).strip(),
        "amount": float(body["amount"]),
        "merchant": str(body["merchant"]).strip(),
        "category": str(body["category"]).strip(),
        "channel": str(body["channel"]).strip(),
        "cardholder_country": str(body.get("cardholder_country", "")).strip(),
        "merchant_country": str(body["merchant_country"]).strip(),
        "device_id": (str(body.get("device_id") or "").strip() or None),
        "ip_address": (str(body.get("ip_address") or "").strip() or None),
    }


def score_new(row: dict, raw_rows: list[dict]) -> ScoredRecord:
    """Score one new row in the context of all existing rows.

    Baselines + aggregates are rebuilt over `raw_rows + [row]` so the new transaction can
    participate in cross-card burst / velocity detection (it might be the txn that *completes*
    a coordinated burst). O(n) over ~1k rows — cheap.
    """
    all_rows = raw_rows + [row]
    baselines = build_card_baselines(all_rows)
    agg = build_aggregates(all_rows)
    return score_row(row, baselines, agg)


def decide(record_dict: dict):
    """Run the decision tree, consulting Gemini only on the borderline branch."""
    score = record_dict.get("fraud_score", 0.0)
    cfg = decision_tree.DEFAULT_CONFIG
    ai_verdict = None
    # Only spend an AI call when the rules are genuinely undecided.
    if cfg.clear_below <= score < cfg.escalate_at:
        fired = {r.get("signal") for r in record_dict.get("reasons", [])}
        if not (fired & cfg.critical_signals):
            ai_verdict = _gemini_classify(record_dict)
    return decision_tree.route(record_dict, ai_verdict=ai_verdict, config=cfg)


def _gemini_classify(record_dict: dict):
    """Indirection so tests can run without importing the Gemini SDK path."""
    try:
        from api import gemini

        return gemini.classify(record_dict)
    except Exception:
        return None
