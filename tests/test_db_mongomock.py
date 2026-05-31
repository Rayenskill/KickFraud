"""MongoDB persistence layer tests against an in-memory mongomock database.

Verifies upsert idempotency, round-trip load, and review-status write-through without
needing a real Atlas connection.
"""
import pytest


@pytest.fixture
def mdb():
    mongomock = pytest.importorskip("mongomock")
    from api import db

    client = mongomock.MongoClient()
    database = client["fraudhunter_test"]
    db.reset_for_tests(database)
    yield db
    db.reset_for_tests(None)


def _doc(tid="tx_x"):
    return {
        "transaction_id": tid, "card_id": "card_001", "amount": 10.0,
        "merchant": "M", "merchant_country": "CA", "category": "grocery",
        "channel": "online", "fraud_score": 0.1, "label": "clear",
        "reasons": [], "card_median": 10.0, "review_status": "pending",
    }


def test_upsert_is_idempotent_and_loads(mdb):
    assert mdb.is_connected()
    mdb.upsert_transaction(_doc())
    mdb.upsert_transaction(_doc())  # same _id -> still one row
    loaded = mdb.load_transactions_from_db()
    assert len(loaded) == 1
    assert loaded[0]["transaction_id"] == "tx_x"
    assert "_id" not in loaded[0]  # stripped for JSON safety


def test_review_status_write_through(mdb):
    mdb.upsert_transaction(_doc("tx_rs"))
    mdb.update_review_status("tx_rs", "approved")
    loaded = {d["transaction_id"]: d for d in mdb.load_transactions_from_db()}
    assert loaded["tx_rs"]["review_status"] == "approved"


def test_audit_insert_and_delete(mdb):
    mdb.insert_audit({"audit_id": "aud_1", "transaction_id": "tx_x", "timestamp": "2026-05-30T00:00:00Z"})
    assert len(mdb.load_audit_from_db()) == 1
    mdb.delete_audit("aud_1")
    assert len(mdb.load_audit_from_db()) == 0
