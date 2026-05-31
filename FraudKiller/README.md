# Fraud Hunter

A triage tool for a human fraud reviewer. It ingests `transactions.csv` (1,000 rows, 50 cards,
~1 month), scores every transaction with an explainable additive engine, and serves a fast,
keyboard-driven review queue with a signature **fraud-ring graph** that makes coordinated,
cross-card attacks visible at a glance.

**v2** adds a business-logic **decision tree** that routes every transaction, optional **Gemini AI**
(reviewer summaries + a borderline tie-breaker), **MongoDB Atlas** persistence with a graceful CSV
fallback, **analyst notifications** on escalation, **live transaction ingestion**, and a richer
filter/sort UI. Every v2 secret is optional — with no `.env`, the app runs exactly as v1 did.

Built for the MCP Hacks / Valsoft 24-hour challenge. Scoring weights: **Detection 40 /
Reviewer experience 40 / Engineering craft 20**, plus up to +5 bonus.

---

## What it does

1. **Ingests** the full CSV and builds per-card baselines + cross-card aggregates in one pass.
2. **Scores** each transaction as a sum of independent, weighted signals. Each signal that fires
   emits a human-readable reason, so every flag is explainable — no black box.
3. **Routes** every transaction through a pure business-logic **decision tree** — `auto_clear` (score
   below 0.42), `queue` for human review, or `escalate` (a critical signal fired, or score ≥ 0.80).
   Escalations set `notify` and fire an analyst alert.
4. **Tie-breaks borderline cases with Gemini** (optional). For scores in `[0.42, 0.80)` with no
   critical signal, Gemini classifies `high`/`low`/`medium` to push toward escalate or queue; with no
   key it falls back to pure rules (defaulting to human review).
5. **Summarizes** each transaction in plain language via Gemini (optional, lazy, cached + persisted)
   — a 1–2 sentence risk narrative with a recommended action.
6. **Labels** each row `fraud` / `clear` against a cost-aware threshold the reviewer can tune live.
7. **Persists to MongoDB Atlas** — transactions, review decisions, audit entries, and notifications.
   Mongo is the source of truth; reads are served from an in-memory cache. With no `MONGO_URI`, the
   app runs CSV-backed in-memory (graceful fallback, logged).
8. **Notifies the analyst** on escalation — records a notification doc in the `notifications`
   collection + audit log. Default transport is **log/queue only** — nothing is actually emailed; a
   pluggable transport seam is left for SMTP/an email API later.
9. **Ingests live transactions** via `POST /transactions` — normalizes the row, rescores against all
   rows including the new one, routes it through the decision tree, and returns the record + decision
   + notification.
10. **Serves** a review queue (one transaction at a time, highest score first) with full context,
    keyboard shortcuts, undo, a richer filter/sort UI, and an in-session feedback loop.
11. **Visualizes** fraud rings as a force-directed graph — the cross-card processor attack shows up
    as hubs linking the 6–7 cards in each coordinated QuickPay burst.
12. **Exports** `transactions_flagged.csv` with `is_fraud`, `fraud_score`, `fraud_reasons` appended.

The detection engine stays **pure** — `detector/` has no web, DB, or network deps and is unit-tested
in isolation. All DB + network code lives in `api/`. The v1 JSON contract is extended **additively**
("contract v2": new optional fields only). See [JSON_CONTRACT.md](JSON_CONTRACT.md).

---

## Quick start (one command from a clean clone)

```bash
# 1. Configure (optional): copy the template and fill in secrets
cp .env.example .env        # add MONGO_URI (Atlas) + optional GEMINI_API_KEY
```

```bash
# 2. Run
# macOS / Linux
./run.sh

# Windows
./run.ps1
```

The script:
1. Creates a Python venv and installs `detector/` + `api/` deps.
2. Seeds MongoDB Atlas from the CSV (`python -m scripts.seed_mongo`) — **skips gracefully** if
   `MONGO_URI` is unset.
3. Starts the FastAPI server (port 8000). On startup it loads transactions from Mongo if connected
   and non-empty, otherwise falls back to scoring `data/transactions.csv` in memory.
4. Installs and starts the React/Vite dev server (port 5173).
5. Opens the browser to the review queue.

**No secrets required.** With an empty or absent `.env`, Mongo seeding is skipped, AI is disabled, and
the app runs CSV-backed in-memory — identical to v1.

Manual run, if you prefer:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
cp .env.example .env                                 # optional: Atlas URI + Gemini key
python -m scripts.seed_mongo                          # optional: seed Atlas (skips if no URI)
uvicorn api.main:app --port 8000                     # API
cd web && npm install && npm run dev                 # UI on :5173
```

`.env.example` documents every variable: `MONGO_URI`, `MONGO_DB` (default `fraudhunter`),
`GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.0-flash`), `FRAUD_ANALYST_EMAIL`,
`NOTIFY_TRANSPORT` (default `log`). All optional; missing secrets degrade gracefully. `.env` is
gitignored.

---

## Repository layout

```
fraud-hunter/
├─ detector/   pure-Python detection engine (no web/DB/network deps)
│  ├─ score.py          scoring pipeline + score_row() for single new txns
│  ├─ signals.py        per-pattern signals
│  ├─ baselines.py      per-card baselines
│  ├─ aggregates.py     cross-card aggregates
│  ├─ decision_tree.py  pure routing: auto_clear / queue / escalate (+notify)
│  └─ schema.py         scored-record dataclasses (contract v2)
├─ api/        FastAPI app, Mongo write-through, AI, notifications, ingest
│  ├─ main.py          endpoints + startup (Mongo-or-CSV)
│  ├─ config.py        .env loader; gemini_enabled() / mongo_configured()
│  ├─ db.py            sync pymongo wrapper (transactions / audit / notifications)
│  ├─ gemini.py        google-genai: summarize() + classify() (lazy, graceful None)
│  ├─ notifications.py notify_analyst() — log/queue only, pluggable _send() seam
│  ├─ ingest.py        normalize_row / score_new / decide for POST /transactions
│  └─ state.py         ReviewState — write-through to Mongo, session undo/suppress
├─ scripts/
│  └─ seed_mongo.py    CSV → score → upsert into Atlas (idempotent)
├─ web/        React + Vite + TypeScript reviewer UI + ring graph
├─ contract/   scored_record.schema.json (contract v2)
├─ tests/      pytest: detection, decision tree, ingest, Gemini fallback, mongomock
├─ data/       transactions.csv
├─ .env.example  documented config template (copy to .env)
└─ docs/       README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES · deep dives
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full module map and data flow, and
[API.md](API.md) for the endpoint reference.

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
[DETECTION.md](DETECTION.md) and [HYPOTHESES.md](HYPOTHESES.md).

The **decision tree** (`detector/decision_tree.py`) consumes scores + fired signals and routes
first-match-wins: a critical signal (`merchant_burst_cross_card`, `amount_vs_card_median`) →
escalate+notify; score ≥ 0.80 → escalate+notify; score < 0.42 → auto-clear; otherwise borderline →
human review, with the optional Gemini verdict able to push `high` → escalate or `low` → queue.

---

## If we had another week

- **Learn weights from labels.** Replace hand-tuned signal weights with logistic regression over
  the same human-readable features, keeping every coefficient interpretable.
- **Real email/SMS transport.** Wire the pluggable `_send()` seam in `notifications.py` to SMTP or an
  email API so escalations actually reach an analyst's inbox, not just the log/notifications queue.
- **Graph analytics.** Run community detection on the ring graph to surface rings we didn't
  hand-encode, and score connected components rather than individual transactions.
- **Reviewer analytics.** Track precision of each analyst's dismissals to calibrate trust and
  auto-route low-risk flags.

---

## Deliverables checklist

- [x] Ingests CSV, processes all 1,000 rows
- [x] Flags with score + label + ranked reasons
- [x] Every flag has ≥1 human-readable reason
- [x] Business-logic decision tree routes every txn (auto-clear / queue / escalate+notify)
- [x] Optional Gemini AI: reviewer summaries + borderline tie-breaker (graceful rule-only fallback)
- [x] MongoDB Atlas persistence (transactions / audit / notifications) with CSV fallback
- [x] Analyst notifications on escalation (log/queue only; pluggable transport seam)
- [x] Live transaction ingestion via `POST /transactions`
- [x] Reviewer path: approve / dismiss / escalate, keyboard nav, undo, filter/sort UI
- [x] README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES
- [x] Updated CSV with fraud marked
- [x] Tests (29 pass): detection, decision tree, ingest, Gemini fallback, mongomock — hermetic, no secrets
- [x] One-command run from clean clone (seeds Mongo, falls back to CSV without secrets)
- [x] Bonus: hypothesis log, audit trail, feedback loop, cost slider, ring graph, AI summaries
