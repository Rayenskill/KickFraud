# IMPLEMENTATION_PLAN

## Stack (locked)
- **Detection + API:** Python, FastAPI. Detector is pure Python with no web/db/network deps so it's
  testable in isolation and reusable — the decision tree (`detector/decision_tree.py`) lives here too.
- **Persistence:** **MongoDB Atlas** via `pymongo` (`pymongo[srv]`) — source of truth + read cache.
  Connected through `MONGO_URI` in `.env`; seeded from the CSV. Missing/unreachable → CSV-backed
  in-memory fallback. See [DATABASE.md](DATABASE.md).
- **Config:** `python-dotenv` (`api/config.py`) loads `.env`. All secrets optional — missing ones
  degrade gracefully.
- **AI (optional):** `google-genai` (Gemini). Plain-language reviewer summaries **and** a borderline
  tie-breaker in the decision tree. Falls back to pure rules when no key.
- **UI:** React + Vite + TypeScript.
- **State:** review/audit/notifications persist to Atlas (write-through); suppression, session weight
  overrides, undo stack, and the cost-slider relabel stay session-scoped in memory.

## Sequencing (24h)

| Window | Work |
|---|---|
| **H0–H2** | Agree and **freeze the JSON contract** (`JSON_CONTRACT.md`). Scaffold all three trees (`detector/`, `api/`, `web/`). Create stub data matching the contract so UI and detector proceed in parallel. |
| **H2–H10** | **Detection and UI in parallel.** Detector: baselines → aggregates → signals → score → flagged CSV; refactor `score_row` out of `score_transactions`; build the pure decision tree. UI: review queue against stub data, keyboard nav, detail pane. |
| **H10–H14** | **Graph + feedback loop + cost slider.** `/graph` endpoint + RingGraph.tsx; dismissal suppression + session weights; threshold endpoint + slider. |
| **H14–H18** | **Tuning + tests + docs.** Tune weights/threshold to F1 ≥ 0.85 against the private fraud band; per-pattern pytest; finish README/PRD/HYPOTHESES. |
| **H18–H24** | **v2 layer.** Atlas via `api/db.py` + `scripts/seed_mongo.py`; `api/config.py`; ingest pipeline (`api/ingest.py`) + `POST /transactions`; Gemini (`api/gemini.py`) + `/transaction/{id}/summary`; notifications (`api/notifications.py`) + `/notifications`; filter/sort UI. Polish, demo script, buffer. |

The H0–H2 contract freeze is the linchpin: it's what lets two or three people build simultaneously
without blocking each other. v2 is extended **additively** ("contract v2") so v1 clients never break.

## What we build
- `detector/` engine with one function per signal, weights as top-of-module constants. `score_row`
  scores a single txn; `build_graph` tolerates dict records; `decision_tree.py` routes scored records
  (**pure** — no web/db/network).
- **Decision tree** — actions `auto_clear | queue | escalate`. `route(record, ai_verdict, config)`,
  first-match-wins:

  | # | Branch | Action |
  |---|---|---|
  | 1 | a critical signal fired (`merchant_burst_cross_card`, `amount_vs_card_median`) | **ESCALATE** + notify |
  | 2 | `score >= escalate_at` (0.80) | **ESCALATE** + notify |
  | 3 | `score < clear_below` (0.42) | **AUTO_CLEAR** |
  | 4 | borderline [0.42, 0.80) | AI `high` → **ESCALATE** + notify; `low` → QUEUE; none/`medium` → QUEUE |

  `notify == True` is the trigger for the analyst alert.
- **FastAPI app** — endpoints:
  - `GET /health` → `{status, records, mongo, gemini}`
  - `GET /transactions` — rich filter (`card_id`, `merchant` substring, `category`, `reason`,
    `channel`, `min_score`/`max_score`, `min_amount`/`max_amount`, `date_from`/`date_to`, `status`,
    `action`) + `sort` (`score_desc` default, `score_asc`, `amount_*`, `date_*`); served from the cache.
  - `GET /transaction/{id}`
  - `GET /transaction/{id}/summary` → `{transaction_id, summary, enabled}` (lazy Gemini, cached + persisted)
  - `POST /transactions` → ingest pipeline; returns `{record, decision, notification}`
  - `GET /notifications` → `{count, results}` (newest-first)
  - `GET /graph`, `POST /review/{id}`, `POST /undo`, `POST /threshold`, `GET /audit`,
    `GET /export` (now populates `cardholder_country`)
- **Atlas layer** — `api/db.py` (collections `transactions` / `audit` / `notifications`; docs keyed
  `_id = transaction_id`, idempotent upsert; write-through helpers). `api/config.py` env loader.
- **Ingest** — `api/ingest.py`: `normalize_row` (required `card_id, amount, merchant, category,
  channel, merchant_country`; auto `transaction_id` + ISO timestamp), `score_new` (rebuild
  baselines/aggregates over all rows incl. the new one, then `score_row`), `decide` (Gemini
  tie-breaker only on the borderline+non-critical branch, else pure `route`).
- **Gemini** — `api/gemini.py`: `summarize` (1–2 sentence risk narrative + action) and `classify`
  (JSON tie-breaker `{risk, confidence, rationale}`); both return `None` without a key.
- **Notifications** — `api/notifications.py`: `notify_analyst` builds a doc, default transport `log`
  records only (**never sends**); `_send()` is the single pluggable seam.
- **Seed** — `scripts/seed_mongo.py`: CSV → score → upsert each into `transactions`
  (`python -m scripts.seed_mongo`; idempotent; skips gracefully if `MONGO_URI` unset).
- React queue + ring graph + filters/sort + cost slider + AI summary panel + ingest form.
- `tests/` (29 green) — decision tree, ingest, Gemini fallback, mongomock, existing detection.
- `run.sh` / `run.ps1` one-command run.
- Docs (this set + [DATABASE.md](DATABASE.md)).

## What we explicitly skip — and why

| Skipped | Why |
|---|---|
| **Trained / opaque ML** | The brief rewards explainability. Additive weighted signals are interpretable and easily tuned; opaque ML is overkill for 1,000 rows and would *lose* points as a black box. Gemini is used only in an **explainable, optional, non-scoring** role (summaries + a logged borderline tie-breaker) — it never replaces or alters the rule scores. |
| **Real email sending** | Escalations are **log/queue only** — recorded in the `notifications` collection + the audit log; nothing is actually emailed. `_send()` is a pluggable seam for SMTP/an email API later. |
| **Auth / multi-user / roles** | Single-reviewer demo. Auth adds zero detection or reviewer-experience value in the judged window. |
| **Mobile / responsive layout** | Reviewer tool is a desktop workflow; the 7-min demo is on a laptop. |
| **Docker / deploy infra** | One-command local run is the requirement. Atlas is managed cloud, so no DB container either; containerization is pure overhead here. |

These cuts are deliberate: they protect time for the two things scored highest — detection quality
and reviewer experience — plus the signature graph and the decision-tree triage.

## Definition of done
- All 1,000 rows scored + labeled + reasoned; `transactions_flagged.csv` written and seeded into Atlas.
- **Decision-tree routing tested** — every branch (critical → escalate, high score → escalate,
  low → auto-clear, borderline → AI/QUEUE) covered.
- **Ingestion pipeline works** — `POST /transactions` normalizes → scores → routes → notifies;
  bust-out escalates + notifies, benign does not.
- **Graceful CSV fallback** — no `MONGO_URI`/unreachable Atlas runs CSV-backed in-memory (logged),
  and no secrets are required for tests (hermetic).
- Queue drivable keyboard-only with undo; feedback loop + audit log working (write-through to Mongo).
- Ring graph renders the QuickPay hub; node-click filters the queue.
- Cost slider re-labels live (cache-only; scores never change).
- **29 tests green** — decision tree, ingest (+ TestClient integration in CSV mode), Gemini fallback,
  mongomock write-through, existing per-pattern detection (fraud above threshold, legit below);
  F1 ≥ 0.85 on the private band.
- `run.sh` / `run.ps1` works from a clean clone (`.env.example` → `.env`).
- Scratch files (`Downloads\_an*.txt`, `/tmp/*.py`) deleted.
