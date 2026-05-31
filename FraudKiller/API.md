# API — FastAPI endpoint reference

The API (`api/main.py`) is the wiring around the pure `detector/`. In **v2** MongoDB Atlas is
the source of truth; reads are served from an in-memory cache (`RECORDS`) so filtering/sorting
never round-trips to Atlas, and writes persist to Mongo *and* update the cache. When `MONGO_URI`
is unset or unreachable the app degrades gracefully to a CSV-backed in-memory fallback, so a
clean clone always runs. All request/response shapes are defined in
[JSON_CONTRACT.md](JSON_CONTRACT.md) (now **contract v2** — additive optional fields only); this
file documents behavior, semantics, and edge cases. See [DATABASE.md](DATABASE.md) for the
persistence model and [ARCHITECTURE.md](ARCHITECTURE.md) for the v2 layering.

## Startup sequence
1. **Load data — Mongo first, CSV fallback.** If Mongo is connected *and* the `transactions`
   collection is non-empty → load docs into the `RECORDS` cache and reconstruct `RAW_ROWS`
   (detector-shaped rows used to rebuild baselines on live ingestion). Else load
   `data/transactions.csv`, run `detector.score_transactions()` once, and hold the result
   in-memory; if Mongo is *connected but empty*, seed it (upsert each doc).
2. Warm caches from persisted state: prime the Gemini summary cache from `ai_summary`, and
   restore non-`pending` `review_status` into `state.py`.
3. Load the **audit log** and **notifications** from Mongo (no-ops in CSV mode).
4. `build_graph()` → graph nodes + edges.
5. Serve. Reads come from `RECORDS`; the source (`mongodb` / `csv (in-memory)` /
   `csv -> seeded mongodb`) is logged.

## Endpoints

### `GET /health`
`{ status, records, mongo, gemini }` — `mongo` is the Atlas connection flag, `gemini` whether a
key + SDK are present.

### `GET /transactions`
Returns scored records, filterable and sortable, served from the in-memory cache for speed.
Labels reflect the **current** threshold and any feedback-loop suppression. This is the queue's
data source.

| Param | Type | Meaning |
|---|---|---|
| `card_id` | string | filter to one card |
| `merchant` | string | substring match |
| `category` | string | exact |
| `reason` | string | rows where a given signal fired |
| `channel` | string | exact (`online` \| `in_person`) |
| `min_score` / `max_score` | float | score range |
| `min_amount` / `max_amount` | float | amount range |
| `date_from` / `date_to` | ISO date | timestamp range (date prefix) |
| `status` | string | `review_status` filter |
| `action` | string | decision-tree action: `auto_clear` \| `queue` \| `escalate` |
| `sort` | string | one of `score_desc`, `score_asc`, `amount_desc`, `amount_asc`, `date_desc`, `date_asc` (default `score_desc`) |

Response: `{ "count": n, "results": [ <scored record>, ... ] }`.

### `GET /transaction/{id}`
Single scored record with full context (`reasons`, `card_median`, current `review_status`). Used
for the detail pane and deep links.

### `GET /transaction/{id}/summary`
Lazy Gemini risk narrative for the reviewer UI. Returns
`{ transaction_id, summary, enabled }` — a 1–2 sentence plain-language verdict + recommended
action, **cached per transaction and persisted** as `ai_summary` once generated. `enabled`
reflects whether Gemini is configured; with no key the SDK call returns `null` and the UI
degrades. Unknown `{id}` → 404.

### `POST /transactions`
Live ingestion pipeline. Body requires `card_id, amount, merchant, category, channel,
merchant_country`; `transaction_id` (`tx_live_<hex>`) and an ISO `timestamp` are auto-assigned if
absent. Steps:
1. `ingest.normalize_row()` — validate/normalize against existing ids (bad body → 422).
2. `ingest.score_new()` — rebuild baselines + aggregates over **all rows including the new one**,
   then `score_row()`.
3. `ingest.decide()` — pure decision tree (`detector/decision_tree.route`); on the
   borderline + non-critical branch it first calls `gemini.classify()` as a tie-breaker.
4. Write through: append to `RAW_ROWS`/`RECORDS`, upsert to Mongo, rebuild the graph.
5. If `decision.notify` → record an analyst notification + a system (decision-tree) audit event.

Response: `{ record, decision, notification }` (`notification` is `null` when no alert fired).
See [DECISION.md](DECISION.md) for the routing tree.

### `GET /notifications`
Returns `{ count, results }`, the analyst alert queue **newest-first**. Alerts are **log/queue
only** — every escalation is recorded (`sent: false`); nothing is actually emailed. `_send()` is
the single pluggable seam left for SMTP/an email API.

### `POST /review/{id}`
Records `approve | dismiss | escalate`. Side effects:
- Updates `review_status` for the transaction **and writes through to the Mongo transaction doc**.
- **Feedback loop:** on `dismiss`, finds *similar* flags (same card+reason, or same merchant-burst
  cluster), marks them suppressed, and nudges the firing signal's session weight down. Returns the
  list of suppressed ids and the new flag count.
- Appends an **audit entry** (reviewer, decision, the reason text shown at decision time,
  timestamp) — inserted into the Mongo `audit` collection.
- Pushes the action onto the **undo stack**.

### `POST /undo`
Pops the last action and fully reverses it: restores the transaction's prior status (write-through
to Mongo), un-suppresses anything that dismissal suppressed, restores the signal weight, and
removes/voids the audit entry (deleted from Mongo). Stack-based, so repeated undo walks back
through history.

### `GET /graph`
Returns nodes (cards + suspicious merchants) and edges (`co_burst`, `shared_ip`, `shared_device`,
plus the faint `transaction` card→merchant backbone edge). The QuickPay-Online co_burst edges form
the demo hubs (May 5 + May 17). See [RING_GRAPH.md](RING_GRAPH.md).

### `POST /threshold`
Accepts an `fp_cost : fn_cost` ratio, recomputes the cutoff, **re-labels in place over fixed
scores** (no re-scoring), and returns old/new flag counts. This relabel is **cache-only — never
persisted; scores never change.** O(rows); feels instant.

### `GET /audit`
Returns the full audit log, newest first (loaded from Mongo at startup, appended on review,
includes decision-tree `system_event` entries). Bonus deliverable; also drives the "watch it
learn" demo beat.

### `GET /export`
Streams `transactions_flagged.csv`. `cardholder_country` is now populated in the export.

## State semantics (`state.py`)
`ReviewState` **writes through to Mongo** for the persistent bits; the rest stays session-scoped.

| State | Backing | Notes |
|---|---|---|
| review-state map | Mongo + cache | `transaction_id → status`; persists `review_status` |
| audit log | Mongo + cache | append-only; insert on review, delete on undo; `system_event()` for decision-tree entries |
| suppression set | in-memory | feedback-loop hidden rows (still in data, excluded from queue) |
| session weight overrides | in-memory | per-signal multipliers nudged by dismissals; reset on restart |
| undo stack | in-memory | ordered list of reversible actions |
| threshold | in-memory | current cutoff + cost ratio; relabel is cache-only |

Mongo is the source of truth; suppression, session weight overrides, and the undo stack remain
session-scoped by design (see [DATABASE.md](DATABASE.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)).

## Errors
- Unknown `{id}` → 404.
- Invalid decision value (or invalid ingest body) → 422.
- `POST /undo` on empty stack → 200 with `{ "undone": null }` (no-op, never errors).
