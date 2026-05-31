"""Seed MongoDB from data/transactions.csv.

Idempotent: every scored record is upserted into the `transactions` collection keyed by
`_id = transaction_id`, so re-running just refreshes scores. Run once after configuring
`.env`, or let run.ps1 / run.sh call it on startup.

    python -m scripts.seed_mongo            # seed from data/transactions.csv
    python -m scripts.seed_mongo path.csv   # seed from a specific file
"""
from __future__ import annotations

import os
import sys

from api import config, db
from detector.io import load_transactions
from detector.score import score_transactions

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CSV = os.path.join(_ROOT, "data", "transactions.csv")


def seed(csv_path: str = _DEFAULT_CSV) -> int:
    if not config.mongo_configured():
        print("MONGO_URI not set — nothing to seed. Set it in .env first.")
        return 1
    if not db.is_connected():
        print("Could not connect to MongoDB. Check MONGO_URI / network.")
        return 1

    rows = load_transactions(csv_path)
    records = score_transactions(rows)
    col = db.transactions_col()

    for record in records:
        db.upsert_transaction(db.record_to_doc(record))

    flagged = sum(1 for r in records if r.label == "fraud")
    total = col.count_documents({})
    print(
        f"seeded {len(records)} records ({flagged} flagged) into "
        f"'{config.MONGO_DB}.{config.TRANSACTIONS_COLLECTION}' — collection now holds {total}."
    )
    return 0


def main(argv: list[str]) -> int:
    csv_path = argv[0] if argv else _DEFAULT_CSV
    return seed(csv_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
