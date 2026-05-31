# DATABASE — MongoDB Atlas persistence

v2 adds a database. Mongo (Atlas, cloud) is the **source of truth** for scored records,
the audit log, and analyst notifications. The detector stays db-free and pure (see
[ARCHITECTURE.md](ARCHITECTURE.md)); all DB code lives in `api/db.py`, wrapped by
`api/state.py` and the ingest pipeline. If Mongo is absent the app still runs — see
[Graceful CSV fallback](#graceful-csv-fallback).

## Collections

| Collection | `_id` | Holds | Written by |
|---|---|---|---|
| `transactions` | `transaction_id` | authoritative scored records | seed, `/review`, `/undo`, `POST /transactions`, summary persist |
| `audit` | auto | append-only decision log (human + decision-tree `system_event`) | `/review`, `/undo`, ingest routing |
| `notifications` | `notification_id` | escalation alert docs (log/queue only — never emailed) | `notify_analyst()` |

`transactions` uses `_id = transaction_id`, so every write is an **idempotent upsert** —
re-seeding or re-ingesting the same id overwrites rather than duplicating.

## Env

Configured in `.env` (copy from `.env.example`; `.gitignore` ignores `.env`). Loaded by
`api/config.py` via `python-dotenv`. All optional — missing values degrade gracefully.

| Var | Default | Meaning |
|---|---|---|
| `MONGO_URI` | _(unset)_ | Atlas SRV connection string. Unset/unreachable → CSV fallback. |
| `MONGO_DB` | `fraudhunter` | database name |

`config.mongo_configured()` reports whether `MONGO_URI` is set. `api/db.py`'s
`is_connected()` pings Atlas **once** at startup; failure → `False` and CSV mode (logged).

## Seeding

`scripts/seed_mongo.py` loads `data/transactions.csv`, runs `score_transactions`, and
upserts each scored record into `transactions`:

```bash
python -m scripts.seed_mongo
```

Idempotent (upsert by `transaction_id`). Prints a skip message and exits cleanly if
`MONGO_URI` is unset, so `run.ps1` / `run.sh` can call it unconditionally on every boot.

## Graceful CSV fallback

A clean clone with no `.env` still runs. When `MONGO_URI` is unset or Atlas is
unreachable, `is_connected()` returns `False` and the app loads `data/transactions.csv`
into memory and scores it — the v1 in-memory path. Writes (`/review`, `/undo`, ingest)
become **no-ops at the DB layer** but still update the in-memory cache, so the UI is fully
functional for a demo; nothing persists across restarts. The mode is logged at startup and
surfaced in `GET /health` (`mongo: true|false`). Tests run hermetically in this mode (plus
`mongomock`), with no secrets.

## Read cache rationale

Mongo is the source of truth, but `/transactions` is **served from an in-memory cache**
(`RECORDS`), not from a per-request Atlas query — filtering and sorting happen over the
cache so there's no round-trip per keystroke. The pattern:

- **Reads** (`GET /transactions`, `/transaction/{id}`) — cache only, never hit Atlas.
- **Writes** (`/review`, `/undo`, `POST /transactions`) — **write through**: update Mongo
  *and* the cache, so the two stay consistent.
- **Threshold relabel** (`POST /threshold`, the cost slider) — **cache only**, never
  persisted. It re-labels over fixed scores; scores never change. See
  [API.md](API.md#post-threshold).
- **AI summary** — lazily generated, cached per `transaction_id`, and persisted to the
  doc as `ai_summary`.

## Startup behavior

`api/main.py` on boot:

1. `is_connected()` pings Atlas once.
2. **Connected & `transactions` non-empty** — load docs into the `RECORDS` cache and
   reconstruct `RAW_ROWS`.
3. **Connected but empty** — seed Mongo from the CSV, then load.
4. **Not connected** — CSV fallback (in-memory).
5. Build the `GRAPH`; load `audit` and `notifications` from Mongo (no-ops in fallback).

## What persists vs. session-scoped

| Persists to Mongo | Session-scoped (in memory only) |
|---|---|
| scored records (`transactions`) | suppression set |
| `review_status` | session signal-weight overrides |
| `ai_summary` | undo stack |
| audit entries (`audit`) | threshold + cost ratio (relabel is cache-only) |
| notifications (`notifications`) | |

## Doc shape

A `transactions` doc — a `ScoredRecord` (contract v2; new optional fields additive — see
[JSON_CONTRACT.md](JSON_CONTRACT.md)) with `_id` pinned to `transaction_id`:

```json
{
  "_id": "tx_000123",
  "transaction_id": "tx_000123",
  "card_id": "card_017",
  "amount": 842.50,
  "merchant": "QuickPay-Online",
  "score": 0.91,
  "reasons": ["merchant_burst_cross_card", "amount_vs_card_median"],
  "review_status": "escalate",
  "cardholder_country": "US",
  "ai_summary": "Cross-card burst at QuickPay-Online far above this card's median — escalate.",
  "decision": { "action": "escalate", "notify": true, "trail": ["..."], "used_ai": false, "reason": "critical signal fired" },
  "notified": true
}
```
