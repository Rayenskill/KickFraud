"""FastAPI endpoints. Shapes are defined in docs/JSON_CONTRACT.md; this file is the wiring.

SCAFFOLD: until detector.score() lands (step 1), startup loads
web/src/stub/transactions.stub.json so the UI builds against real contract-shaped data in
parallel. Swap the marked block in load_state() for detector.score(io.load_transactions(...)).
"""
from __future__ import annotations

import io
import os
import csv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.state import ReviewState
from detector.io import load_transactions, RAW_COLUMNS, FLAGGED_EXTRA_COLUMNS
from detector.score import score_transactions, build_graph

app = FastAPI(title="Fraud Hunter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state, populated at startup.
RECORDS: list[dict] = []
GRAPH: dict = {"nodes": [], "edges": []}
STATE = ReviewState()
THRESHOLD = 0.42

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_state() -> None:
    global RECORDS, GRAPH
    
    csv_path = os.path.join(_ROOT, "data", "transactions.csv")
    rows = load_transactions(csv_path)
    scored_records = score_transactions(rows)
    
    RECORDS = [r.to_dict() for r in scored_records]
    GRAPH = build_graph(scored_records, rows)


@app.on_event("startup")
def _startup() -> None:
    load_state()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "records": len(RECORDS)}


@app.get("/transactions")
def list_transactions(
    card_id: str | None = None,
    merchant: str | None = None,
    category: str | None = None,
    reason: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    status: str | None = None,
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
    if reason:
        out = [r for r in out if any(x["signal"] == reason for x in r["reasons"])]
    if min_score is not None:
        out = [r for r in out if r["fraud_score"] >= min_score]
    if max_score is not None:
        out = [r for r in out if r["fraud_score"] <= max_score]
    if status:
        out = [r for r in out if r["review_status"] == status]
        
    out = sorted(out, key=lambda r: r["fraud_score"], reverse=(sort != "score_asc"))
    return {"count": len(out), "results": out}


@app.get("/transaction/{tid}")
def get_transaction(tid: str) -> dict:
    for r in RECORDS:
        if r["transaction_id"] == tid:
            d = r.copy()
            d["review_status"] = STATE.status.get(tid, "pending")
            return d
    raise HTTPException(status_code=404, detail="unknown transaction_id")


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
    
    new_flag_count = sum(
        1 for r in RECORDS 
        if r["label"] == "fraud" 
        and r["transaction_id"] not in STATE.suppressed 
        and STATE.status.get(r["transaction_id"], "pending") == "pending"
    )
    res["new_flag_count"] = new_flag_count
    
    return res


@app.post("/undo")
def undo() -> dict:
    res = STATE.undo()
    if not res:
        return {"undone": None}
        
    new_flag_count = sum(
        1 for r in RECORDS 
        if r["label"] == "fraud" 
        and r["transaction_id"] not in STATE.suppressed 
        and STATE.status.get(r["transaction_id"], "pending") == "pending"
    )
    res["new_flag_count"] = new_flag_count
    
    return res


@app.post("/threshold")
def set_threshold(body: dict) -> dict:
    global THRESHOLD, RECORDS
    fp_cost = body.get("fp_cost", 1)
    fn_cost = body.get("fn_cost", 5)
    
    ratio = fn_cost / fp_cost
    
    old_flag_count = sum(
        1 for r in RECORDS 
        if r["label"] == "fraud" 
        and r["transaction_id"] not in STATE.suppressed 
        and STATE.status.get(r["transaction_id"], "pending") == "pending"
    )
    
    if fp_cost == 1 and fn_cost == 5:
        THRESHOLD = 0.42
    else:
        THRESHOLD = max(0.1, min(1.0, 0.6 - (ratio * 0.036)))
        
    for r in RECORDS:
        r["label"] = "fraud" if r["fraud_score"] >= THRESHOLD else "clear"
        
    new_flag_count = sum(
        1 for r in RECORDS 
        if r["label"] == "fraud" 
        and r["transaction_id"] not in STATE.suppressed 
        and STATE.status.get(r["transaction_id"], "pending") == "pending"
    )
    
    return {
        "threshold": round(THRESHOLD, 2),
        "old_flag_count": old_flag_count,
        "new_flag_count": new_flag_count
    }


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
