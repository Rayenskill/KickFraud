"""CSV load + flagged-CSV write.

Raw CSV columns (data/transactions.csv), in file order:
    transaction_id, timestamp, card_id, amount, merchant_name, merchant_category,
    channel, cardholder_country, merchant_country, device_id, ip_address

Notes verified against the data (docs/CORRECTIONS.md, docs/DATA_ANALYSIS.md):
  - transaction_id is a STRING ("tx_000784"); device_id / ip_address may be empty.
  - There is NO is_fraud column. The injected-fraud band is the high-id range
    tx_000919..tx_001007 (~77 rows). Use it as a PRIVATE recall/precision check only —
    never as a shipped signal.
  - The contract renames merchant_name->merchant and merchant_category->category.
"""
from __future__ import annotations

import csv

RAW_COLUMNS = [
    "transaction_id", "timestamp", "card_id", "amount", "merchant_name",
    "merchant_category", "channel", "cardholder_country", "merchant_country",
    "device_id", "ip_address",
]

# Columns appended to the exported deliverable, in order.
FLAGGED_EXTRA_COLUMNS = ["is_fraud", "fraud_score", "fraud_reasons"]

# Private validation band (check only — see module docstring).
FRAUD_BAND = ("tx_000919", "tx_001007")


def load_transactions(path: str) -> list[dict]:
    """Read the raw CSV into typed dict rows (amount->float; empty device/ip->None).

    Renames merchant_name->merchant and merchant_category->category for
    downstream code to match the frozen JSON contract.
    """
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row = {
                "transaction_id": raw["transaction_id"].strip(),
                "timestamp": raw["timestamp"].strip(),
                "card_id": raw["card_id"].strip(),
                "amount": float(raw["amount"]),
                "merchant": raw["merchant_name"].strip(),          # renamed
                "category": raw["merchant_category"].strip(),      # renamed
                "channel": raw["channel"].strip(),
                "cardholder_country": raw["cardholder_country"].strip(),
                "merchant_country": raw["merchant_country"].strip(),
                "device_id": raw["device_id"].strip() or None,
                "ip_address": raw["ip_address"].strip() or None,
            }
            rows.append(row)
    return rows


def write_flagged_csv(records: list, path: str) -> None:
    """Re-emit all rows with is_fraud / fraud_score / fraud_reasons appended.

    `records` is a list of ScoredRecord dataclass instances.
    fraud_reasons is the ranked reason texts joined by '; '.
    """
    fieldnames = RAW_COLUMNS + FLAGGED_EXTRA_COLUMNS
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            reason_texts = "; ".join(
                (reason.text if hasattr(reason, "text") else reason["text"])
                for reason in (r.reasons if hasattr(r, "reasons") else r.get("reasons", []))
            )
            score = r.fraud_score if hasattr(r, "fraud_score") else r.get("fraud_score", 0.0)
            label = r.label if hasattr(r, "label") else r.get("label", "clear")
            writer.writerow({
                "transaction_id": r.transaction_id if hasattr(r, "transaction_id") else r["transaction_id"],
                "timestamp": r.timestamp if hasattr(r, "timestamp") else r["timestamp"],
                "card_id": r.card_id if hasattr(r, "card_id") else r["card_id"],
                "amount": r.amount if hasattr(r, "amount") else r["amount"],
                "merchant_name": r.merchant if hasattr(r, "merchant") else r["merchant"],
                "merchant_category": r.category if hasattr(r, "category") else r["category"],
                "channel": r.channel if hasattr(r, "channel") else r["channel"],
                "cardholder_country": getattr(r, "cardholder_country", None) or r.get("cardholder_country", "") if isinstance(r, dict) else getattr(r, "cardholder_country", ""),
                "merchant_country": r.merchant_country if hasattr(r, "merchant_country") else r["merchant_country"],
                "device_id": (r.device_id if hasattr(r, "device_id") else r.get("device_id")) or "",
                "ip_address": (r.ip_address if hasattr(r, "ip_address") else r.get("ip_address")) or "",
                "is_fraud": label == "fraud",
                "fraud_score": round(score, 4),
                "fraud_reasons": reason_texts,
            })
