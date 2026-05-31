"""FastAPI endpoints. Shapes are defined in docs/JSON_CONTRACT.md (v2); this file is the wiring.

Data source: MongoDB Atlas when `MONGO_URI` is configured and reachable, otherwise a
CSV-backed in-memory fallback (so a clean clone always runs). Reads are served from an
in-memory cache (`RECORDS`) for snappy filtering/sorting; writes persist to Mongo *and*
update the cache. See docs/DATABASE.md and docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import io
import os
import csv
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api import config, db, gemini, ingest, notifications
from api.state import ReviewState
from detector.io import load_transactions, RAW_COLUMNS, FLAGGED_EXTRA_COLUMNS
from detector.score import score_transactions, build_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fraudhunter.api")

app = FastAPI(title="Fraud Hunter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory caches, populated at startup. RECORDS = scored-record dicts served to the UI;
# RAW_ROWS = detector-shaped rows used to rebuild baselines/aggregates on live ingestion.
RECORDS: list[dict] = []
RAW_ROWS: list[dict] = []
GRAPH: dict = {"nodes": [], "edges": []}
STATE = ReviewState()
THRESHOLD = 0.42

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_RAW_ROW_KEYS = [
    "transaction_id", "timestamp", "card_id", "amount", "merchant", "category",
    "channel", "cardholder_country", "merchant_country", "device_id", "ip_address",
]


def _doc_to_row(doc: dict) -> dict:
    """Project a stored transaction doc back to a detector-shaped raw row."""
    return {k: doc.get(k) for k in _RAW_ROW_KEYS}


def load_state() -> None:
    global RECORDS, RAW_ROWS, GRAPH

    docs = db.load_transactions_from_db()  # None if Mongo not connected; [] if empty
    if docs:
        RECORDS = docs
        RAW_ROWS = [_doc_to_row(d) for d in docs]
        for d in docs:                       # warm caches from persisted state
            if d.get("ai_summary"):
                gemini.cache_summary(d["transaction_id"], d["ai_summary"])
            st = d.get("review_status", "pending")
            if st and st != "pending":
                STATE.status[d["transaction_id"]] = st
        STATE.load_audit(db.load_audit_from_db())
        notifications.load_from_mongo()
        source = "mongodb"
    else:
        csv_path = os.path.join(_ROOT, "data", "transactions.csv")
        rows = load_transactions(csv_path)
        scored = score_transactions(rows)
        RECORDS = [db.record_to_doc(r) for r in scored]
        RAW_ROWS = rows
        source = "csv (in-memory)"
        if db.is_connected():            # connected but empty -> seed it
            for doc in RECORDS:
                db.upsert_transaction(doc)
            source = "csv -> seeded mongodb"

    GRAPH = build_graph(RECORDS, RAW_ROWS)
    logger.info("Loaded %d records from %s.", len(RECORDS), source)


@app.on_event("startup")
def _startup() -> None:
    load_state()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "records": len(RECORDS),
        "mongo": db.is_connected(),
        "gemini": config.gemini_enabled(),
    }


_SORTERS = {
    "score_desc": ("fraud_score", True),
    "score_asc": ("fraud_score", False),
    "amount_desc": ("amount", True),
    "amount_asc": ("amount", False),
    "date_desc": ("timestamp", True),
    "date_asc": ("timestamp", False),
}


@app.get("/transactions")
def list_transactions(
    card_id: str | None = None,
    merchant: str | None = None,
    category: str | None = None,
    reason: str | None = None,
    channel: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    action: str | None = None,
    sort: str = "score_desc",
) -> dict:
    out = [r for r in RECORDS if r["transaction_id"] not in STATE.suppressed]

    for r in out:
        r["review_status"] = STATE.status.get(r["transaction_id"], "pending")

    if card_id:
        out = [r for r in out if r["card_id"] == card_id]
    if merchant:
        out = [r for r in out if merchant.lower() in r["merchant"].lower()]
    if category:
        out = [r for r in out if r["category"] == category]
    if channel:
        out = [r for r in out if r["channel"] == channel]
    if reason:
        out = [r for r in out if any(x["signal"] == reason for x in r["reasons"])]
    if min_score is not None:
        out = [r for r in out if r["fraud_score"] >= min_score]
    if max_score is not None:
        out = [r for r in out if r["fraud_score"] <= max_score]
    if min_amount is not None:
        out = [r for r in out if r["amount"] >= min_amount]
    if max_amount is not None:
        out = [r for r in out if r["amount"] <= max_amount]
    if date_from:
        out = [r for r in out if (r.get("timestamp") or "")[:10] >= date_from]
    if date_to:
        out = [r for r in out if (r.get("timestamp") or "")[:10] <= date_to]
    if status:
        out = [r for r in out if r["review_status"] == status]
    if action:
        out = [r for r in out if (r.get("decision") or {}).get("action") == action]

    key, rev = _SORTERS.get(sort, _SORTERS["score_desc"])
    out = sorted(out, key=lambda r: r.get(key, 0), reverse=rev)
    return {"count": len(out), "results": out}


@app.get("/transaction/{tid}")
def get_transaction(tid: str) -> dict:
    for r in RECORDS:
        if r["transaction_id"] == tid:
            d = r.copy()
            d["review_status"] = STATE.status.get(tid, "pending")
            return d
    raise HTTPException(status_code=404, detail="unknown transaction_id")


@app.get("/transaction/{tid}/summary")
def transaction_summary(tid: str) -> dict:
    """Lazy Gemini risk summary for the reviewer UI. Cached + persisted once generated."""
    rec = next((r for r in RECORDS if r["transaction_id"] == tid), None)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown transaction_id")
    text = gemini.summarize(rec)
    if text:
        rec["ai_summary"] = text
        db.update_summary(tid, text)
    return {"transaction_id": tid, "summary": text, "enabled": config.gemini_enabled()}


@app.post("/transactions")
def create_transaction(body: dict) -> dict:
    """Ingest a new transaction: score it, run the decision tree, maybe alert the analyst.

    This is the live path the brief's "another week: streaming ingestion" item becomes.
    """
    global GRAPH
    try:
        row = ingest.normalize_row(body, {r["transaction_id"] for r in RECORDS})
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    record = ingest.score_new(row, RAW_ROWS)
    doc = db.record_to_doc(record)
    doc["label"] = "fraud" if doc["fraud_score"] >= THRESHOLD else "clear"

    decision = ingest.decide(doc)            # rules + (borderline) Gemini tie-breaker
    doc["decision"] = decision.to_dict()
    doc["notified"] = decision.notify

    RAW_ROWS.append(row)
    RECORDS.append(doc)
    db.upsert_transaction(doc)

    notification = None
    if decision.notify:
        notification = notifications.notify_analyst(doc, decision)
        STATE.system_event(doc["transaction_id"], decision.action, decision.reason)

    GRAPH = build_graph(RECORDS, RAW_ROWS)
    return {"record": doc, "decision": decision.to_dict(), "notification": notification}


@app.get("/notifications")
def list_notifications() -> dict:
    items = notifications.list_notifications()
    return {"count": len(items), "results": items}


@app.get("/graph")
def get_graph() -> dict:
    return GRAPH


@app.post("/review/{tid}")
def review(tid: str, body: dict) -> dict:
    decision = body.get("decision")
    reviewer = body.get("reviewer", "system")

    if decision not in ("approve", "dismiss", "escalate"):
        raise HTTPException(status_code=422, detail="Invalid decision")

    txn = next((r for r in RECORDS if r["transaction_id"] == tid), None)
    if not txn:
        raise HTTPException(status_code=404, detail="unknown transaction_id")

    res = STATE.record(txn, RECORDS, decision, reviewer)

    res["new_flag_count"] = _pending_flag_count()
    return res


@app.post("/undo")
def undo() -> dict:
    res = STATE.undo()
    if not res:
        return {"undone": None}

    res["new_flag_count"] = _pending_flag_count()
    return res


@app.post("/threshold")
def set_threshold(body: dict) -> dict:
    global THRESHOLD
    fp_cost = body.get("fp_cost", 1)
    fn_cost = body.get("fn_cost", 5)

    ratio = fn_cost / fp_cost
    old_flag_count = _pending_flag_count()

    if fp_cost == 1 and fn_cost == 5:
        THRESHOLD = 0.42
    else:
        THRESHOLD = max(0.1, min(1.0, 0.6 - (ratio * 0.036)))

    # Live re-label over fixed scores (cache only — not persisted; scores never change).
    for r in RECORDS:
        r["label"] = "fraud" if r["fraud_score"] >= THRESHOLD else "clear"

    return {
        "threshold": round(THRESHOLD, 2),
        "old_flag_count": old_flag_count,
        "new_flag_count": _pending_flag_count(),
    }


def _pending_flag_count() -> int:
    return sum(
        1 for r in RECORDS
        if r["label"] == "fraud"
        and r["transaction_id"] not in STATE.suppressed
        and STATE.status.get(r["transaction_id"], "pending") == "pending"
    )


@app.get("/audit")
def audit() -> dict:
    return {"entries": list(reversed(STATE.audit_log))}


@app.get("/export")
def export() -> StreamingResponse:
    output = io.StringIO()
    fieldnames = RAW_COLUMNS + FLAGGED_EXTRA_COLUMNS
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in RECORDS:
        reason_texts = "; ".join(reason["text"] for reason in r["reasons"])
        writer.writerow({
            "transaction_id": r["transaction_id"],
            "timestamp": r["timestamp"],
            "card_id": r["card_id"],
            "amount": r["amount"],
            "merchant_name": r["merchant"],
            "merchant_category": r["category"],
            "channel": r["channel"],
            "cardholder_country": r.get("cardholder_country", ""),
            "merchant_country": r["merchant_country"],
            "device_id": r.get("device_id") or "",
            "ip_address": r.get("ip_address") or "",
            "is_fraud": r["label"] == "fraud",
            "fraud_score": round(r["fraud_score"], 4),
            "fraud_reasons": reason_texts,
        })

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_flagged.csv"}
    )
