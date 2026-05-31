"""Live-ingestion pipeline tests.

Two layers:
  * function-level (no DB, no network) for normalize/score/decide;
  * an endpoint integration test through FastAPI's TestClient in CSV-fallback mode,
    asserting an escalating transaction produces a persisted-in-memory notification.
"""
import os

import pytest

from api import ingest
from detector.io import load_transactions

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CSV = os.path.join(_ROOT, "data", "transactions.csv")
_ROWS = load_transactions(_CSV)


# --- function-level -------------------------------------------------------

def test_normalize_autoassigns_id_and_timestamp():
    row = ingest.normalize_row({
        "card_id": "card_001", "amount": 10, "merchant": "X",
        "category": "grocery", "channel": "online", "merchant_country": "CA",
    })
    assert row["transaction_id"].startswith("tx_")
    assert row["timestamp"]


def test_normalize_missing_required_raises():
    with pytest.raises(ValueError):
        ingest.normalize_row({"card_id": "card_001"})


def test_bustout_scores_and_escalates():
    row = ingest.normalize_row({
        "card_id": "card_001", "amount": 99999, "merchant": "MegaElectronics",
        "category": "gift_card", "channel": "online", "merchant_country": "CA",
    })
    rec = ingest.score_new(row, _ROWS)
    assert rec.fraud_score > 0
    decision = ingest.decide(rec.to_dict())
    assert decision.action == "escalate"
    assert decision.notify is True


# --- endpoint integration (CSV-fallback, no Mongo, no Gemini) -------------

@pytest.fixture
def client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from api import config, db, gemini, notifications

    monkeypatch.setattr(config, "MONGO_URI", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    db.reset_for_tests(None)          # force CSV-backed in-memory mode
    gemini._client = None
    gemini._client_init = True        # force AI disabled (no network)
    notifications.NOTIFICATIONS.clear()

    from api.main import app
    with TestClient(app) as c:
        yield c


def test_ingest_missing_field_returns_422(client):
    resp = client.post("/transactions", json={"card_id": "card_001"})
    assert resp.status_code == 422


def test_ingest_bustout_escalates_and_notifies(client):
    resp = client.post("/transactions", json={
        "card_id": "card_001", "amount": 99999, "merchant": "MegaElectronics",
        "category": "gift_card", "channel": "online", "merchant_country": "CA",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"]["action"] == "escalate"
    assert data["decision"]["notify"] is True
    assert data["notification"] is not None

    notifs = client.get("/notifications").json()
    assert notifs["count"] >= 1
    assert notifs["results"][0]["transaction_id"] == data["record"]["transaction_id"]


def test_ingest_benign_does_not_notify(client):
    resp = client.post("/transactions", json={
        "card_id": "card_001", "amount": 9.25, "merchant": "Tim Hortons",
        "category": "restaurant", "channel": "in_person", "merchant_country": "CA",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"]["action"] in ("auto_clear", "queue")
    assert data["decision"]["notify"] is False
    assert data["notification"] is None
