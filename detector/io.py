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

    TODO (step 1): csv.DictReader; coerce amount to float; map merchant_name->merchant
    and merchant_category->category for downstream code; keep timestamp as ISO string.
    """
    raise NotImplementedError("detector.io.load_transactions — step 1")


def write_flagged_csv(records: list, path: str) -> None:
    """Re-emit all rows with is_fraud / fraud_score / fraud_reasons appended.

    TODO (step 1): join scored records onto raw rows by transaction_id; fraud_reasons is
    the ranked reason texts joined by '; '.
    """
    raise NotImplementedError("detector.io.write_flagged_csv — step 1")
