# Fraud Hunter

A triage tool for a human fraud reviewer. It ingests `transactions.csv` (1,000 rows, 50 cards,
~1 month), scores every transaction with an explainable additive engine, and serves a fast,
keyboard-driven review queue with a signature **fraud-ring graph** that makes coordinated,
cross-card attacks visible at a glance.

Built for the MCP Hacks / Valsoft 24-hour challenge. Scoring weights: **Detection 40 /
Reviewer experience 40 / Engineering craft 20**, plus up to +5 bonus.

---

## What it does

1. **Ingests** the full CSV and builds per-card baselines + cross-card aggregates in one pass.
2. **Scores** each transaction as a sum of independent, weighted signals. Each signal that fires
   emits a human-readable reason, so every flag is explainable — no black box.
3. **Labels** each row `fraud` / `clear` against a cost-aware threshold the reviewer can tune live.
4. **Serves** a review queue (one transaction at a time, highest score first) with full context,
   keyboard shortcuts, undo, search/filter, and an in-session feedback loop.
5. **Visualizes** fraud rings as a force-directed graph — the cross-card processor attack shows up
   as hubs linking the 6–7 cards in each coordinated QuickPay burst.
6. **Exports** `transactions_flagged.csv` with `is_fraud`, `fraud_score`, `fraud_reasons` appended.

---

## Quick start (one command from a clean clone)

```bash
# macOS / Linux
./run.sh

# Windows
./run.ps1
```

The script:
1. Creates a Python venv and installs `detector/` + `api/` deps.
2. Runs the detector once over `data/transactions.csv` → produces scored records + `transactions_flagged.csv`.
3. Starts the FastAPI server (port 8000).
4. Installs and starts the React/Vite dev server (port 5173).
5. Opens the browser to the review queue.

Manual run, if you prefer:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
python -m detector.score data/transactions.csv      # writes transactions_flagged.csv
uvicorn api.main:app --port 8000                     # API
cd web && npm install && npm run dev                 # UI on :5173
```

---

## Repository layout

```
fraud-hunter/
├─ detector/   pure-Python detection engine (no web deps)
├─ api/        FastAPI app, in-memory state, audit log
├─ web/        React + Vite + TypeScript reviewer UI + ring graph
├─ tests/      pytest: known-fraud + known-legit per pattern
├─ data/       transactions.csv
└─ docs/       README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES · deep dives
```

See `docs/ARCHITECTURE.md` for the full module map and data flow.

---

## Detection strategy (short version)

We reverse-engineered four fraud patterns from the data and built one signal per pattern, plus a
few cheap defensive signals. Detection is **grounded in observed structure**, not guessed:

| Pattern | What it looks like | Signal |
|---|---|---|
| P1 Card-testing micro-bursts | ~8–12 tiny online txns in ~25 min (sub-2-min micro-clusters) | per-card velocity: ≥4 small online txns in ~10–15 min |
| P2 Account-takeover foreign spree | sudden foreign online_retail on a card that never shops foreign | atypical category **and** country (no date) |
| P3 Gift-card / electronics bust-out | 1–3 buys at 12×–55× the card median | amount-vs-median outlier + high-risk category |
| P4 Coordinated processor attack | two bursts of 6–7 cards >$200 at "QuickPay Online" (~72 min each) | cross-card merchant burst: ≥5 cards / merchant / ~2h, each >$200 |

The two big traps we explicitly avoid: geo-mismatch alone (mostly legit CA→US Amazon) and a
foreign `merchant_country` alone (Spotify=SE, AliExpress=CN are legitimately foreign). We require
*combined* deviations and per-card baselines instead of absolute thresholds. Full reasoning in
`docs/DETECTION.md` and `docs/HYPOTHESES.md`.

---

## If we had another week

- **Learn weights from labels.** Replace hand-tuned signal weights with logistic regression over
  the same human-readable features, keeping every coefficient interpretable.
- **Persist review decisions** to a real store and turn the in-session feedback loop into a
  durable, cross-session analyst model.
- **Streaming ingestion.** Score transactions as they arrive with incremental baseline updates
  rather than a single batch pass.
- **Graph analytics.** Run community detection on the ring graph to surface rings we didn't
  hand-encode, and score connected components rather than individual transactions.
- **Reviewer analytics.** Track precision of each analyst's dismissals to calibrate trust and
  auto-route low-risk flags.

---

## Deliverables checklist

- [x] Ingests CSV, processes all 1,000 rows
- [x] Flags with score + label + ranked reasons
- [x] Every flag has ≥1 human-readable reason
- [x] Reviewer path: approve / dismiss / escalate, keyboard nav, undo
- [x] README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES
- [x] Updated CSV with fraud marked
- [x] ≥1 meaningful test (known fraud + known legit per pattern)
- [x] One-command run from clean clone
- [x] Bonus: hypothesis log, audit trail, feedback loop, cost slider, ring graph
