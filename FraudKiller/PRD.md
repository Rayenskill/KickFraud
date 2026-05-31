# PRD — Fraud Hunter

> **v2.** Adds a business-logic decision tree, Gemini AI (explainable summaries + a
> borderline tie-breaker), MongoDB Atlas persistence, analyst notifications, and live
> transaction ingestion on top of the v1 detector + queue + ring graph. The frozen v1
> JSON contract is extended **additively only** — see [JSON_CONTRACT.md](JSON_CONTRACT.md).

## 1. Problem

A human fraud reviewer receives a stream of transactions and must decide, quickly and defensibly,
which are fraudulent. Today that means scanning raw rows with no prioritization, no context, and no
explanation. We are given `transactions.csv` (1,000 rows, 50 cards, ~1 month, ~7% fraud across four
hidden patterns) and must ship a tool that tells the reviewer **what to look at first, why it's
suspicious, and lets them act on it in seconds** — and now routes the obvious cases automatically so
the reviewer only spends attention where it matters.

## 2. Goals

- **G1 — Catch the fraud.** Detect the four patterns present in the data with high F1 (target ≥0.85),
  without over-flagging legitimate foreign / geo-mismatched activity.
- **G2 — Make every flag explainable.** Each flagged transaction carries a ranked list of plain-
  language reasons. A reviewer never sees a score with no justification.
- **G3 — Make review fast.** A reviewer can triage a flag in a few seconds, keyboard-only, with full
  context on one screen and instant undo.
- **G4 — Reveal coordinated fraud.** Cross-card attacks that are invisible per-transaction become
  obvious through the ring graph.
- **G5 — Be honest engineering.** One-command run, tests per pattern, clear docs, no black box.

## 3. Non-goals (explicitly out of scope)

- Auth, multi-user, roles.
- Mobile / responsive layout.
- Containerization (Docker), deployment infra.
- **Opaque ML scoring.** Scores still come from the transparent weighted-signal detector. AI is used
  only for explanation and as a tie-breaker — never as a black-box scorer (see §5 *AI assist*).
- **Actually sending email.** Escalations are logged/queued only; a transport seam is left for SMTP
  / an email API later (see §5 *Notifications*).

Rationale for each is recorded in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

> **Moved into scope in v2** — formerly non-goals: a database (now MongoDB Atlas, the source of
> truth), live ingestion of new transactions, and AI assistance (Gemini, explainable only).

## 4. Users & primary use case

**Primary user: the fraud reviewer.** Sits down with a queue of flagged transactions, works
highest-risk first, and for each one decides **approve** (it's fraud / take action), **dismiss**
(false positive), or **escalate** (needs a second look). They want context and speed, not a
spreadsheet. In v2 the obvious cases never reach them — the decision tree auto-clears clean
transactions and auto-escalates the dangerous ones, queuing only the genuinely borderline ones for
human judgment.

**Core loop:**
1. Open the tool → queue is pre-sorted by score, highest first.
2. Read the top flag: amount vs the card's normal spend, the ranked reasons, recent history, and the
   plain-language AI summary + routing chip.
3. Press `A` / `D` / `E`. The decision is logged (to Mongo) and the queue auto-advances.
4. Occasionally: open the ring graph to understand a coordinated cluster, adjust the cost slider, or
   simulate an incoming transaction and watch it route + notify.

## 5. Functional requirements

### Detection
- **FR-D1** Process all 1,000 rows; produce a score and label for every row.
- **FR-D2** Score = sum of independent weighted signals; label = `fraud` if score ≥ threshold.
- **FR-D3** Each fired signal emits a human-readable reason string.
- **FR-D4** Detect P1–P4 (see [DETECTION.md](DETECTION.md)).
- **FR-D5** Avoid the geo-mismatch and foreign-country traps (require combined deviations).
- **FR-D6** Export `transactions_flagged.csv` with `is_fraud`, `fraud_score`, `fraud_reasons`
  (export now also populates `cardholder_country`).
- **FR-D7** `score_row()` scores a single transaction against prebuilt baselines + aggregates, so a
  newly ingested row can be scored without re-running the whole batch. `detector/` stays
  **web-free and db-free** — pure and unit-testable.

### Decision tree (routing)
The decision tree lives in `detector/decision_tree.py` — pure, no web/db/network. `route(record,
ai_verdict=None, config)` returns a `Decision{action, notify, trail[], used_ai, reason}`.

Defaults — `clear_below=0.42`, `escalate_at=0.80`, critical signals
`{merchant_burst_cross_card, amount_vs_card_median}`.

| Order | Branch | Action | `notify` |
| --- | --- | --- | --- |
| 1 | a critical signal fired | `escalate` | ✓ |
| 2 | score ≥ `escalate_at` (0.80) | `escalate` | ✓ |
| 3 | score < `clear_below` (0.42) | `auto_clear` | — |
| 4 | borderline `[0.42, 0.80)`, AI verdict `high` | `escalate` | ✓ |
| 4 | borderline, AI verdict `low` | `queue` | — |
| 4 | borderline, AI `medium`/none | `queue` (default to human) | — |

- **FR-T1** First match wins; the branch order above is fixed.
- **FR-T2** `auto_clear` and `escalate` resolve without a reviewer; `queue` is the only path that
  surfaces in the human review queue.
- **FR-T3** `notify == True` is the single trigger for an analyst alert (see *Notifications*).
- **FR-T4** Every route records `trail[]` + `reason`; routing-tree decisions log to the audit trail
  as **system events** (non-human actor).

### AI assist (Gemini, explainable only)
`api/gemini.py` (google-genai SDK, lazy, model from `GEMINI_MODEL`). All calls return `None` when no
key / SDK missing / call fails, so rules + UI degrade gracefully.

- **FR-AI1** `summarize(record)` → a 1–2 sentence plain-language risk narrative + recommended action.
  Cached per `transaction_id` and persisted as `ai_summary`.
- **FR-AI2** `classify(record)` → `{risk, confidence, rationale}` — a JSON verdict used **only** as
  the tie-breaker on the borderline branch of the decision tree. Gemini never produces the score.
- **FR-AI3** No API key → rules-only: summaries are absent, the tie-breaker defaults to `queue`.

### Ingestion (live transactions)
`api/ingest.py` + `POST /transactions`.

- **FR-I1** `normalize_row(body, existing_ids)` validates required fields `card_id, amount, merchant,
  category, channel, merchant_country`; auto-assigns `transaction_id` (`tx_live_<hex>`) and an ISO
  timestamp when absent.
- **FR-I2** `score_new(row, raw_rows)` rebuilds baselines + aggregates over **all** rows including the
  new one, then scores via `score_row()`.
- **FR-I3** `decide(record_dict)` runs the decision tree — on the borderline + non-critical branch it
  calls `gemini.classify()` first, otherwise pure `route()`.
- **FR-I4** `POST /transactions` runs the pipeline and returns `{record, decision, notification}`; the
  scored record is upserted to Mongo and the cache is updated.

### Notifications / alerting
`api/notifications.py`. Transport is **log/queue only** — nothing is ever emailed in v2.

- **FR-N1** When a route sets `notify == True`, `notify_analyst(record, decision)` builds a
  `Notification{notification_id, transaction_id, to, subject, body, action, score, transport,
  created_at, sent}`.
- **FR-N2** Default transport `log` records the doc with `sent=False` and never sends. `_send()` is
  the single pluggable seam (smtp / api are unimplemented stubs).
- **FR-N3** Notifications are kept in an in-memory list mirrored to the Mongo `notifications`
  collection; `GET /notifications` returns them newest-first.
- **FR-N4** `FRAUD_ANALYST_EMAIL` (default `fraud-analyst@example.com`) is the recipient on the doc.

### Reviewer experience
- **FR-R1** Queue presents one flag at a time, sorted by score descending.
- **FR-R2** Single-screen context: amount vs card median, ranked reasons, card recent history,
  mini ring snippet, AI summary, and the decision-tree routing chip.
- **FR-R3** Keyboard: `A` approve, `D` dismiss, `E` escalate, `J/K` or `←/→` navigate, `U` undo,
  `/` focus search. Decision auto-advances.
- **FR-R4** Undo (stack-based) with toast confirmation on every decision.
- **FR-R5** Filter by `card_id`, `merchant` (substring), `category`, `reason` (signal fired),
  `channel`, `min_score`/`max_score`, `min_amount`/`max_amount`, `date_from`/`date_to`, `status`,
  `action`; sort in `{score_desc, score_asc, amount_desc, amount_asc, date_desc, date_asc}`
  (default `score_desc`). Served from the in-memory cache (no per-keystroke Atlas round-trip).
- **FR-R6** Cost-aware slider (FP $ vs FN $) re-labels live and shows the count delta. The relabel is
  **cache-only** — never persisted; scores never change.
- **FR-R7** In-session feedback loop: dismissing suppresses similar flags and nudges that signal's
  weight down for the session. Suppression set, weight overrides, and the undo stack stay in memory.
- **FR-R8** Audit log records every decision (who/when/what/reason), persisted to Mongo; system
  (decision-tree) events are recorded too.
- **FR-R9** "Simulate incoming transaction" form with presets (Ring burst, Bust-out, Clear) posts to
  the ingestion endpoint and demonstrates routing → notification.

### Graph
- **FR-G1** Force-directed graph; nodes = cards + suspicious merchants; edges = shared IP, shared
  device, co-burst, plus a faint `transaction` card→merchant backbone edge.
- **FR-G2** The QuickPay-Online bursts (May 5 + May 17) render as visible hubs.
- **FR-G3** Click a node → filter the queue to its transactions.

### Persistence
- **FR-P1** MongoDB Atlas is the **source of truth** (collections: `transactions`, `audit`,
  `notifications`); connected via `MONGO_URI`, seeded from the CSV (`python -m scripts.seed_mongo`,
  idempotent).
- **FR-P2** Reads are served from an in-memory cache loaded at startup. Writes (review, undo, ingest)
  write through to Mongo **and** the cache. `transactions` docs use `_id = transaction_id`
  (idempotent upsert).
- **FR-P3** Graceful fallback: if `MONGO_URI` is unset or Atlas is unreachable, the app runs
  CSV-backed in-memory (logged). DB + network code lives only in `api/`.
- **FR-P4** Persisted: `review_status`, audit entries, notifications. Session-scoped (memory only):
  suppression set, weight overrides, undo stack, and the cost-slider relabel.

## 6. Success metrics

- Detection F1 ≥ 0.85 against the privately-known fraud band (validation aid only).
- A reviewer can clear a flag in < 5 seconds keyboard-only.
- The decision tree auto-clears / auto-escalates the obvious cases, queuing only borderline rows.
- Ring graph renders the QuickPay hub legibly within the 7-minute demo.
- One-command run succeeds from a clean clone on a fresh machine — with no secrets, the app still
  boots (CSV fallback, rules-only, log-only notifications).

## 7. Demo narrative (7 min)

Load queue → explain one flag's reasons and read its AI summary → open ring graph, the two QuickPay
rings appear → simulate a Bust-out transaction and watch it auto-escalate + raise a notification, then
a Clear one auto-clears → dismiss a flag and watch similar flags get suppressed → move the cost slider
and watch the flagged count change. Full script in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
