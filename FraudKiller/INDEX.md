# Fraud Hunter — documentation index

Deep-dive docs for every aspect of the build plan.

## Core deliverable docs (map to the brief)
- **[CORRECTIONS.md](CORRECTIONS.md)** — ⚠️ read first: plan-claim vs. verified-data deltas after
  re-checking `transactions.csv`. The dates/counts in the original plan were wrong; this is the
  authoritative correction.
- **[README.md](README.md)** — what it is, one-command run, strategy summary, "another week" section.
- **[PRD.md](PRD.md)** — problem, goals, non-goals, users, functional requirements, success metrics.
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** — stack, 24h sequencing, what we skip and why,
  definition of done.
- **[HYPOTHESES.md](HYPOTHESES.md)** — the fraud hypothesis log (bonus): every signal and every trap,
  with verdicts.

## Detection
- **[DATA_ANALYSIS.md](DATA_ANALYSIS.md)** — what's actually in the CSV: the four patterns, the traps,
  the validation aid.
- **[DETECTION.md](DETECTION.md)** — the scoring engine: pipeline, signals, weights, explanation,
  cost-aware threshold, tuning. `score_row()` now scores a single txn for live ingest.

## System
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — module map and data flow. `detector/` stays pure (web-free,
  db-free); DB + network live in `api/`.
- **[JSON_CONTRACT.md](JSON_CONTRACT.md)** — the frozen schema both sides build against. Read this
  before writing any detector output or UI fetch. **Contract v2** extends it additively (new optional
  fields only: `cardholder_country`, `ai_summary`, `decision`, `notified`).
- **[API.md](API.md)** — FastAPI endpoint reference, state semantics, errors. Includes the v2
  filter/sort params, `/transaction/{id}/summary`, `POST /transactions`, and `/notifications`.

## Pipeline & operations (v2)
The business-logic + AI + persistence layer added in v2. `detector/` stays pure; DB and network
code lives in `api/`. All secrets are optional — missing keys degrade gracefully to CSV-backed,
rules-only behavior.

- **[DECISION_TREE.md](DECISION_TREE.md)** — pure routing logic (`detector/decision_tree.py`):
  `auto_clear` / `queue` / `escalate`, the branch order, critical signals, and where the Gemini
  tie-breaker plugs in. `notify == True` is the analyst-alert trigger.
- **[GEMINI.md](GEMINI.md)** — `api/gemini.py`: lazy `summarize()` reviewer narratives (cached +
  persisted as `ai_summary`) and `classify()` JSON tie-breaker verdicts. Returns `None` with no key
  / SDK missing / call failure, so rules + UI keep working.
- **[DATABASE.md](DATABASE.md)** — MongoDB Atlas persistence (`api/db.py`): collections
  (`transactions`, `audit`, `notifications`), the in-memory cache + write-through model, idempotent
  upsert (`_id = transaction_id`), graceful CSV fallback, and `scripts/seed_mongo.py`.
- **[NOTIFICATIONS.md](NOTIFICATIONS.md)** — `api/notifications.py`: log/queue-only analyst
  escalations (`notify_analyst`), the notification doc shape, and the single pluggable `_send()`
  transport seam (SMTP / email API left as stubs — nothing is ever emailed).

## Reviewer experience
- **[REVIEWER_UX.md](REVIEWER_UX.md)** — the queue, keyboard model, undo, feedback loop, audit log,
  plus the v2 filter/sort UI, the lazy AI-summary panel, and the "simulate incoming transaction" form.
- **[RING_GRAPH.md](RING_GRAPH.md)** — the signature fraud-ring graph feature.

## Process
- **[TESTING.md](TESTING.md)** — detection tests, run test, reviewer flow, CSV check, plus the v2
  hermetic suite (decision tree, ingest, Gemini fallback, mongomock write-through) — runs with no
  secrets.
- **[RISKS.md](RISKS.md)** — risks and mitigations.
- **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)** — the 7-minute demo, beat by beat.
- **[TEAM_SPLIT.md](TEAM_SPLIT.md)** — how to divide work across 3 people + 3 Claude + 1 Codex.

## Suggested reading order
1. README → PRD (what & why)
2. DATA_ANALYSIS → HYPOTHESES → DETECTION (how detection is grounded)
3. ARCHITECTURE → JSON_CONTRACT → API (the system spine)
4. DECISION_TREE → GEMINI → DATABASE → NOTIFICATIONS (the v2 pipeline & operations layer)
5. REVIEWER_UX → RING_GRAPH (the 40-point experience + wow feature)
6. IMPLEMENTATION_PLAN → TEAM_SPLIT → TESTING → RISKS → DEMO_SCRIPT (execution)
