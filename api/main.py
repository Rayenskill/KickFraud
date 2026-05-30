"""FastAPI endpoints. Shapes are defined in docs/JSON_CONTRACT.md; this file is the wiring.

SCAFFOLD: until detector.score() lands (step 1), startup loads
web/src/stub/transactions.stub.json so the UI builds against real contract-shaped data in
parallel. Swap the marked block in load_state() for detector.score(io.load_transactions(...)).
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.state import ReviewState

app = FastAPI(title="Fraud Hunter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state, populated at startup.
RECORDS: list[dict] = []
GRAPH: dict = {"nodes": [], "edges": []}
STATE = ReviewState()
THRESHOLD = 0.42

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STUB = os.path.join(_ROOT, "web", "src", "stub")


def load_state() -> None:
    global RECORDS, GRAPH
    # --- SCAFFOLD START (replace with detector.score in step 1/2) ---------
    with open(os.path.join(_STUB, "transactions.stub.json"), encoding="utf-8") as fh:
        RECORDS = json.load(fh)
    with open(os.path.join(_STUB, "graph.stub.json"), encoding="utf-8") as fh:
        GRAPH = json.load(fh)
    # --- SCAFFOLD END -----------------------------------------------------


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
    out = RECORDS
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
            return r
    raise HTTPException(status_code=404, detail="unknown transaction_id")


@app.get("/graph")
def get_graph() -> dict:
    return GRAPH


@app.post("/review/{tid}")
def review(tid: str, body: dict) -> dict:
    # TODO (step 2): STATE.record(tid, decision, reviewer) + feedback-loop suppression
    # + audit append; return {transaction_id, review_status, suppressed, new_flag_count, audit_id}.
    raise HTTPException(status_code=501, detail="review — step 2")


@app.post("/undo")
def undo() -> dict:
    # TODO (step 2): STATE.undo(); empty stack -> {"undone": null} (200, no error).
    raise HTTPException(status_code=501, detail="undo — step 2")


@app.post("/threshold")
def set_threshold(body: dict) -> dict:
    # TODO (step 3): body {fp_cost, fn_cost} -> recompute cutoff, relabel in place over
    # fixed scores, return {threshold, old_flag_count, new_flag_count}.
    raise HTTPException(status_code=501, detail="threshold — step 3")


@app.get("/audit")
def audit() -> dict:
    return {"entries": list(reversed(STATE.audit_log))}


@app.get("/export")
def export() -> dict:
    # TODO (step 2): stream transactions_flagged.csv from current in-memory labels.
    raise HTTPException(status_code=501, detail="export — step 2")
