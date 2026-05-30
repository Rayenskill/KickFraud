# TESTING & VERIFICATION

Four verification tracks: detection correctness, one-command run, reviewer flow, and the deliverable
CSV.

---

## 1. Detection (`pytest`, `tests/`)

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

Run: `pytest -q`

---

## 2. One-command run
From a **clean clone**: `./run.sh` (or `./run.ps1`) builds the detector output and serves API + web.
Open the browser and confirm:
- the queue loads with reasons on each flag, and
- the ring graph renders the QuickPay hub.

This is a hard requirement in the brief; test it on a machine that hasn't built the project before.

---

## 3. Reviewer flow (manual)
- Drive the queue **keyboard-only**: `A`/`D`/`E` to decide, `J/K` to navigate, `U` to undo.
- Confirm a **dismissal suppresses similar flags** and the flag count drops.
- Confirm the dismissal **appears in the audit log** with its reason.
- Move the **cost slider** and watch the flagged count change live.
- Click a **graph node** and confirm the queue filters to its transactions.

---

## 4. Deliverable CSV
Open `transactions_flagged.csv` and confirm `is_fraud`, `fraud_score`, `fraud_reasons` are populated
for **all 1,000 rows** (not just the flagged ones — clears carry score + empty/`clear` reasons too).

---

## Regression discipline
After any weight/threshold change, re-run `pytest` so a tuning tweak that helps one pattern can't
silently break another or re-open a trap.
