"""MongoDB (Atlas) access layer — the authoritative store for scored transactions,
the audit log, and analyst notifications.

Design notes
------------
- This is the ONLY place that talks to Mongo. `detector/` stays db-free (pure + testable).
- Sync `pymongo` is used because the FastAPI endpoints in `api/main.py` are sync `def`.
- **Graceful fallback is a feature, not an accident.** If `MONGO_URI` is unset or Atlas is
  unreachable, `is_connected()` returns False and the API runs in CSV-backed in-memory
  mode (see `api/main.py:load_state`). The judged "one-command run from a clean clone"
  must never hard-fail just because a secret is missing.
- `transactions` documents use `_id = transaction_id` so seeding/inserts are idempotent
  upserts.
"""
from __future__ import annotations

import logging

from api import config

logger = logging.getLogger("fraudhunter.db")

_client = None
_db = None
_connected = False
_init_done = False


def _init() -> None:
    """Lazily create the client and ping Atlas exactly once."""
    global _client, _db, _connected, _init_done
    if _init_done:
        return
    _init_done = True

    if not config.mongo_configured():
        logger.warning("MONGO_URI not set — running in CSV-backed in-memory mode.")
        return

    try:
        from pymongo import MongoClient

        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=4000)
        # Force a round-trip so an unreachable cluster fails fast, here, not mid-request.
        _client.admin.command("ping")
        _db = _client[config.MONGO_DB]
        _connected = True
        logger.info("Connected to MongoDB database '%s'.", config.MONGO_DB)
    except Exception as exc:  # ImportError, ServerSelectionTimeoutError, auth, ...
        _client = None
        _db = None
        _connected = False
        logger.warning("MongoDB unavailable (%s) — falling back to in-memory mode.", exc)


def is_connected() -> bool:
    _init()
    return _connected


def get_db():
    """Return the Database handle, or None when running in fallback mode."""
    _init()
    return _db


def transactions_col():
    db = get_db()
    return db[config.TRANSACTIONS_COLLECTION] if db is not None else None


def audit_col():
    db = get_db()
    return db[config.AUDIT_COLLECTION] if db is not None else None


def notifications_col():
    db = get_db()
    return db[config.NOTIFICATIONS_COLLECTION] if db is not None else None


def reset_for_tests(db) -> None:
    """Inject a (mongomock) database in tests. Bypasses the real connection."""
    global _client, _db, _connected, _init_done
    _client = None
    _db = db
    _connected = db is not None
    _init_done = True


# --- document helpers + persistence ops (all no-op when not connected) -----

def record_to_doc(record) -> dict:
    """A ScoredRecord (or already-dict) -> a Mongo/cache document.

    Includes `cardholder_country` (not a contract field but needed for CSV export) and a
    default `review_status`. The `_id` is added at write time (= transaction_id).
    """
    if hasattr(record, "to_dict"):
        doc = record.to_dict()
        doc["cardholder_country"] = getattr(record, "cardholder_country", "") or ""
    else:
        doc = dict(record)
        doc.setdefault("cardholder_country", "")
    doc.setdefault("review_status", "pending")
    return doc


def upsert_transaction(doc: dict) -> None:
    col = transactions_col()
    if col is None:
        return
    tid = doc["transaction_id"]
    col.replace_one({"_id": tid}, {**doc, "_id": tid}, upsert=True)


def load_transactions_from_db() -> list[dict] | None:
    """All transaction docs (without _id), or None if not connected."""
    col = transactions_col()
    if col is None:
        return None
    out: list[dict] = []
    for d in col.find():
        d.pop("_id", None)
        out.append(d)
    return out


def update_review_status(tid: str, status: str) -> None:
    col = transactions_col()
    if col is not None:
        col.update_one({"_id": tid}, {"$set": {"review_status": status}})


def update_summary(tid: str, text: str) -> None:
    col = transactions_col()
    if col is not None:
        col.update_one({"_id": tid}, {"$set": {"ai_summary": text}})


def insert_audit(entry: dict) -> None:
    col = audit_col()
    if col is not None:
        col.insert_one(dict(entry))


def delete_audit(audit_id: str) -> None:
    col = audit_col()
    if col is not None:
        col.delete_one({"audit_id": audit_id})


def load_audit_from_db() -> list[dict]:
    col = audit_col()
    if col is None:
        return []
    out: list[dict] = []
    for d in col.find().sort("timestamp", 1):
        d.pop("_id", None)
        out.append(d)
    return out
