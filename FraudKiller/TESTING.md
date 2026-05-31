# TESTING & VERIFICATION

Eight verification tracks: detection correctness, the decision tree, the ingestion pipeline, Gemini
fallback, the MongoDB layer, one-command run, reviewer flow, and the deliverable CSV.

The automated suite is **29 tests** and runs **hermetically — no secrets, no network**. Mongo is
faked with `mongomock`; Gemini is exercised only in its no-key path. Run the whole thing with:

```
pytest -q
```

---

## 1. Detection (`pytest`, `tests/test_detection.py`)

**Per-pattern assertions** — at least one known fraud and one known legit per pattern:

| Case | Expectation |
|---|---|
| `tx_000920` (card_016, $1,900 electronics, 30× median, P3) | scores **above** threshold, label `fraud` |
| `tx_000957` (card_049 micro-burst, May 14 21:46, P1) | scores **above** threshold |
| `tx_001005` (card_037, $311 QuickPay, May 17 burst, P4) | scores **above** threshold |
| `tx_000870` (card_047 AliExpress, P2 account-takeover) | scores **above** threshold |
| `tx_000551` (a normal Tim Hortons in-person txn) | scores **below** threshold, label `clear` |
| `tx_000231` (Amazon.com CA→US, $8.84 — geo-mismatch trap) | scores **below** threshold |
| any Spotify SE / a lone foreign txn on a foreign-regular card (foreign-country trap) | scores **below** threshold |

The two trap cases are as important as the fraud cases: they prove we don't over-flag.

**Signal unit tests:** each signal function tested in isolation with crafted inputs (it fires when it
should, emits the right reason, and is silent otherwise). Because weights are top-of-module
constants, tests assert behavior independent of the exact weight values.

**Precision/recall harness (private):** cross-check the flagged set against the known fraud band
(tx_000919–tx_001007) to compute precision/recall/F1. Target **F1 ≥ 0.85**. This harness lives in
the test tree, **never in `signals.py`** — the transaction_id band is a validation aid, not a
feature (see `HYPOTHESES.md` H8). Tune weights/threshold until F1 is in range.

This suite is unchanged in v2 and **still green** — `detector/` stays web-free and db-free, so its
tests never touch Mongo or Gemini.

---

## 2. Decision tree (`tests/test_decision_tree.py`)

`detector/decision_tree.py` is pure (no web/db/network), so every branch of `route()` is unit-tested
directly against crafted `Decision` outputs. Branch order is **first match wins**, and there is a test
per branch:

| Branch | Input | Expect |
|---|---|---|
| 1 — critical signal | a `critical_signals` reason fired (`merchant_burst_cross_card` / `amount_vs_card_median`) | `escalate`, `notify==True` |
| 2 — high score | `score ≥ escalate_at` (0.80) | `escalate`, `notify==True` |
| 3 — low score | `score < clear_below` (0.42) | `auto_clear`, `notify==False` |
| 4a — borderline + AI high | score in [0.42, 0.80), `ai_verdict="high"` | `escalate`, `notify==True`, `used_ai==True` |
| 4b — borderline + AI low | score in [0.42, 0.80), `ai_verdict="low"` | `queue`, `notify==False` |
| 4c — borderline, no/medium AI | score in [0.42, 0.80), `ai_verdict` `None`/`"medium"` | `queue` (default to human review) |

Tests assert the full `Decision` shape — `action`, `notify`, `trail[]`, `used_ai`, `reason` — and
that `notify==True` is set **exactly** on the escalate branches (it is the trigger for the analyst
alert). The critical-signal branch is checked to win over a sub-`escalate_at` score, proving order.

---

## 3. Ingestion pipeline (`tests/test_ingest.py`)

Covers the three `api/ingest.py` stages plus a live integration:

**Unit — `normalize_row(body, existing_ids)`**
- required fields present (`card_id`, `amount`, `merchant`, `category`, `channel`,
  `merchant_country`) → row built; missing one → rejected.
- no `transaction_id` → auto-assigns `tx_live_<hex>`; no timestamp → ISO timestamp injected.

**Unit — `score_new(row, raw_rows)`** — baselines + aggregates are rebuilt over **all rows including
the new one**, then `score_row()` runs; a planted bust-out scores high, a planted benign scores low.

**Unit — `decide(record_dict)`** — on the borderline + non-critical branch it calls `gemini.classify`
then `route()`; otherwise it calls `route()` purely (no AI). With no key, classify returns `None`, so
borderline defaults to `queue`.

**Integration — FastAPI `TestClient`, CSV mode (no Mongo, no key):**

| Scenario | POST `/transactions` body | Expect |
|---|---|---|
| Bust-out | a row that trips a critical signal / high score | `decision.action == "escalate"`, `notification` present, `notified` true; a doc in `/notifications` |
| Benign | a clearly-normal row | `decision.action` in `{auto_clear, queue}`, **no** escalation, **no** notification |

The integration asserts the full response envelope `{record, decision, notification}` and that the
benign case does **not** add to `/notifications`. Because Mongo is unconfigured, the app runs
CSV-backed in-memory and the writes are no-ops — the test stays hermetic.

---

## 4. Gemini graceful fallback (`tests/test_gemini_fallback.py`)

`api/gemini.py` must degrade silently when there is no key, the SDK is missing, or a call fails:

- `summarize(record)` → `None` when `GEMINI_API_KEY` is unset.
- `classify(record)` → `None` when `GEMINI_API_KEY` is unset.
- with no key, `config.gemini_enabled()` is `False` and the `/transaction/{id}/summary` envelope
  reports `enabled: false` with `summary: null`.

These run with **no key set**, so they exercise only the offline path — never a real API call. The
point: rules + UI keep working without Gemini, and the decision tree falls back to pure rules.

---

## 5. MongoDB layer (`tests/test_db_mongomock.py`)

`api/db.py` is exercised against a `mongomock` client via `reset_for_tests(db)` — no Atlas, no
network. See [DATABASE.md](DATABASE.md) for the persistence model.

- **Upsert idempotency** — `upsert_transaction` keys on `_id = transaction_id`; upserting the same
  scored record twice leaves **one** doc with the latest values (a re-seed never duplicates).
- **Write-through** — a review decision updates the transaction doc's `review_status` and inserts an
  audit entry; `update_summary` persists `ai_summary`; `insert_audit` / `delete_audit` round-trip
  and `load_audit_from_db` reads them back. `load_transactions_from_db` reconstructs the cache.

Mirrors the runtime rule: **Mongo is the source of truth, reads are served from the in-memory cache,
writes write through.** With Mongo unconfigured at runtime these helpers are graceful no-ops, which
is why tracks 3–4 stay hermetic.

---

## 6. One-command run
From a **clean clone**: `./run.sh` (or `./run.ps1`) installs the venv + deps, runs
`python -m scripts.seed_mongo` (which **skips gracefully** if `MONGO_URI` is unset), builds the
detector output, and serves API (`:8000`) + web (`:5173`). Open the browser and confirm:
- the queue loads with reasons on each flag,
- the ring graph renders the QuickPay hub, and
- `GET /health` reports `{status, records, mongo, gemini}` — `mongo`/`gemini` simply read `false`
  when unconfigured.

This is a hard requirement in the brief; test it on a machine that hasn't built the project before,
**with and without** a `.env`.

---

## 7. Reviewer flow (manual)
- Drive the queue **keyboard-only**: `A`/`D`/`E` to decide, `J/K` to navigate, `U` to undo.
- Confirm a **dismissal suppresses similar flags** and the flag count drops.
- Confirm the dismissal **appears in the audit log** with its reason.
- Move the **cost slider** and watch the flagged count change live (relabel is cache-only — scores
  never change, nothing persists).
- Click a **graph node** and confirm the queue filters to its transactions.
- Use **Simulate incoming transaction** (`IngestForm`) presets — Ring burst, Bust-out, Clear — and
  confirm the decision-tree chip + the notification appear for the escalating presets only.

---

## 8. Deliverable CSV
Open `transactions_flagged.csv` and confirm `is_fraud`, `fraud_score`, `fraud_reasons` are populated
for **all 1,000 rows** (not just the flagged ones — clears carry score + empty/`clear` reasons too).
`GET /export` additionally populates `cardholder_country` (contract v2; see
[JSON_CONTRACT.md](JSON_CONTRACT.md)).

---

## Regression discipline
After any weight/threshold change, re-run `pytest` so a tuning tweak that helps one pattern can't
silently break another or re-open a trap. After any decision-tree, ingest, or DB change, re-run the
full **29-test** suite — the tracks are coupled through `route()` and the write-through cache.
