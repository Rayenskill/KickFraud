# API — FastAPI endpoint reference

The API (`api/main.py`) loads `data/transactions.csv` once at startup, runs `detector.score()` once,
and holds scored records + graph edges + a mutable review-state map in memory (`api/state.py`). No
database. All request/response shapes are defined in `JSON_CONTRACT.md`; this file documents
behavior, semantics, and edge cases.

## Startup sequence
1. Load CSV → list of raw transactions.
2. `detector.score()` → scored records, graph edges, and write `transactions_flagged.csv`.
3. Initialize `state.py`: review-state map (all `pending`), empty undo stack, empty audit log,
   default threshold, default signal weights.
4. Serve.

## Endpoints

### `GET /transactions`
Returns scored records, filterable and sortable (params in `JSON_CONTRACT.md`). Labels reflect the
**current** threshold and any feedback-loop suppression. Default sort: score descending. This is the
queue's data source.

### `GET /transaction/{id}`
Single scored record with full context (`reasons`, `card_median`, current `review_status`). Used for
the detail pane and deep links.

### `POST /review/{id}`
Records `approve | dismiss | escalate`. Side effects:
- Updates `review_status` for the transaction.
- **Feedback loop:** on `dismiss`, finds *similar* flags (same card+reason, or same merchant-burst
  cluster), marks them suppressed, and nudges the firing signal's session weight down. Returns the
  list of suppressed ids and the new flag count.
- Appends an **audit entry** (reviewer, decision, the reason text shown at decision time, timestamp).
- Pushes the action onto the **undo stack**.

### `POST /undo`
Pops the last action and fully reverses it: restores the transaction's prior status, un-suppresses
anything that dismissal suppressed, restores the signal weight, and removes/voids the audit entry.
Stack-based, so repeated undo walks back through history.

### `GET /graph`
Returns nodes (cards + suspicious merchants) and edges (`co_burst`, `shared_ip`, `shared_device`).
The QuickPay-Online co_burst edges form the demo hubs (May 5 + May 17). See `RING_GRAPH.md`.

### `POST /threshold`
Accepts an `fp_cost : fn_cost` ratio, recomputes the cutoff, **re-labels in place over fixed scores**
(no re-scoring), and returns old/new flag counts. O(rows); feels instant.

### `GET /audit`
Returns the full audit log, newest first. Bonus deliverable; also drives the "watch it learn" demo
beat.

### `GET /export`
Streams `transactions_flagged.csv`.

## State semantics (`state.py`)
- **review-state map:** `transaction_id → status`.
- **suppression set:** transactions hidden by the feedback loop (still in data, excluded from the
  active queue).
- **session weight overrides:** per-signal multipliers nudged by dismissals; reset on restart.
- **undo stack:** ordered list of reversible actions.
- **audit log:** append-only list of decisions.
- **threshold:** current cutoff + the cost ratio that produced it.

Everything is in-memory and session-scoped by design (see `IMPLEMENTATION_PLAN.md`).

## Errors
- Unknown `{id}` → 404.
- Invalid decision value → 422.
- `POST /undo` on empty stack → 200 with `{ "undone": null }` (no-op, never errors).
