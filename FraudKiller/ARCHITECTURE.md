# ARCHITECTURE

## Module map

```
fraud-hunter/
├─ detector/                pure-Python detection engine (no web/db/network deps)
│  ├─ baselines.py          per-card profiles: median/MAD amount, categories, country, channels,
│  │                        devices/IPs, hour-of-day
│  ├─ aggregates.py         cross-card maps: (merchant,day) distinct-card counts + amount stats,
│  │                        IP→cards, device→cards, rolling per-card velocity windows
│  ├─ signals.py            one function per signal + weight constants + reason strings
│  ├─ score.py              orchestrates: csv → scored records + graph edges + flagged csv.
│  │                        score_row() (single-txn scoring) extracted from score_transactions;
│  │                        build_graph tolerant of dict records
│  ├─ decision_tree.py      PURE business-logic router: route() → auto_clear | queue | escalate,
│  │                        with notify flag + trail. Gemini verdict is an optional tie-breaker
│  ├─ schema.py             dataclasses mirroring the contract (now v2)
│  └─ io.py                 load csv, write transactions_flagged.csv
├─ api/                     FastAPI — all DB + network code lives here
│  ├─ main.py               endpoints; startup loads from Mongo (or CSV fallback) into the cache
│  ├─ state.py              review decisions + session weight overrides + audit; WRITES THROUGH
│  │                        to Mongo (review_status + audit); suppression/overrides/undo in-memory
│  ├─ config.py             python-dotenv env loader; gemini_enabled() / mongo_configured()
│  ├─ db.py                 sync pymongo wrapper; collections transactions/audit/notifications
│  ├─ gemini.py             google-genai: summarize() narrative + classify() tie-breaker (lazy)
│  ├─ notifications.py      notify_analyst(); LOG/QUEUE-only transport with a pluggable seam
│  └─ ingest.py             live-txn pipeline: normalize_row → score_new → decide
├─ scripts/seed_mongo.py    CSV → score → upsert into Mongo (idempotent; skips if no MONGO_URI)
├─ web/                     React + Vite + TypeScript
│  ├─ ReviewQueue.tsx       one-card-at-a-time triage, keyboard-driven, undo
│  ├─ RingGraph.tsx         force-directed fraud-ring graph (signature feature)
│  ├─ Filters.tsx           search + sort dropdown + advanced filter grid + cost slider
│  ├─ AiSummary.tsx         lazy Gemini panel + decision-tree routing chip
│  ├─ IngestForm.tsx        "Simulate incoming transaction" with presets
│  ├─ types.ts              TS mirror of the contract (now v2)
│  └─ api.ts                typed client for the API
├─ tests/                   pytest: detection + decision tree + ingest + gemini fallback + mongomock
├─ data/transactions.csv
├─ transactions_flagged.csv generated deliverable
├─ contract/scored_record.schema.json  the frozen schema both sides build against (now v2)
├─ docs/                    README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES · deep dives
├─ .env.example             copy → .env (MONGO_URI, GEMINI_API_KEY, …); .env gitignored
└─ run.sh / run.ps1         one-command: venv+deps → seed_mongo → start API + web
```

## Data flow

```
                                   startup
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ▼                                                            ▼
  Mongo connected & transactions non-empty             no Mongo (CSV fallback)
        │                                                            │
  load docs → RECORDS cache                          data/transactions.csv
  + reconstruct RAW_ROWS                             → detector.score()
        │                                                            │
        └──────────────────────────┬─────────────────────────────────┘
                                    ▼
                  in-memory: RECORDS cache + RAW_ROWS + GRAPH
                  + session review-state map (state.py)
                  + audit + notifications loaded from Mongo
                                    │
   ┌────────────────┬──────────────┼──────────────┬──────────────────┐
   ▼                ▼              ▼              ▼                  ▼
GET /transactions  GET /graph   POST /review   POST /threshold   POST /transactions
GET /transaction…  GET /audit   POST /undo     (cache relabel)   (ingest pipeline)
GET …/summary      GET /export  GET /notifications
   │  (reads served from cache)        │ (writes write-through to Mongo + cache)
   └──────────────────────── React (web/) ────────────────────────────┘
        ReviewQueue · RingGraph · Filters · AiSummary · IngestForm
```

```
ingestion pipeline  (POST /transactions)
   body ─▶ normalize_row(body, existing_ids)   assigns tx_live_<hex> + ISO ts if absent
        ─▶ score_new(row, RAW_ROWS)            rebuild baselines+aggregates INCLUDING new row,
        │                                       then score_row()
        ─▶ decide(record)                      decision_tree.route(); on the borderline,
        │                                       non-critical branch first calls gemini.classify()
        ─▶ if decision.notify ─▶ notify_analyst(record, decision)  (LOG/QUEUE only)
        ─▶ persist: upsert txn + system_event audit + notification → Mongo + cache
        ─▶ rebuild GRAPH
   returns { record, decision, notification }
```

1. **Source of truth:** MongoDB Atlas (connected via `MONGO_URI`) holds `transactions`, `audit`,
   and `notifications`. Transaction docs use `_id = transaction_id` for idempotent upsert.
2. **Startup:** if Mongo is connected and `transactions` is non-empty, load the docs into the
   `RECORDS` cache and reconstruct `RAW_ROWS`; otherwise fall back to the CSV via
   `detector.score()` (and seed Mongo if it is connected-but-empty). Build `GRAPH`. Load audit +
   notifications from Mongo.
3. **Read:** React fetches `/transactions` (filterable/sortable) and `/graph` — served from the
   in-memory cache, so no per-keystroke Atlas round-trip. `…/summary` lazily calls Gemini, caches,
   and persists `ai_summary`.
4. **Act:** decisions to `/review/{id}` (and `/undo`) write through — they update the doc's
   `review_status` and insert/delete audit entries — and update the cache.
5. **Ingest:** `/transactions` runs the pipeline above, routes via the decision tree, may notify
   the analyst, persists, and rebuilds the graph.
6. **Tune:** `/threshold` re-labels in place over fixed scores — **cache-only, never persisted**.
7. **Export:** `/export` streams `transactions_flagged.csv` (now populates `cardholder_country`).

## Why Mongo + an in-memory read cache

Atlas is the **source of truth** — review decisions, audit entries, notifications, and ingested
transactions survive restarts. But 1,000 rows fit trivially in memory, so reads are served from an
in-memory cache loaded once at startup: filtering, sorting, and the ring graph stay instant with no
per-keystroke round-trip. Writes (review, undo, ingest) **write through** to Mongo *and* update the
cache, keeping both consistent. The cost-slider threshold relabel is cache-only — scores never
change, so it stays O(rows) and feels live.

**Graceful fallback:** if `MONGO_URI` is unset or Atlas is unreachable, `db.is_connected()` pings
once, returns `False` (logged), and the app runs CSV-backed in memory — writes become no-ops, but
detection, triage, the graph, and ingest all still work. Likewise Gemini degrades to pure rules when
no key is present. Nothing is ever emailed: notifications are LOG/QUEUE-only with a pluggable
`_send()` seam left for SMTP or an email API later. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
for the full "what we skip and why" rationale, and [API.md](API.md) for state semantics.

## The JSON contract is the spine (now v2)

The detector and the UI are built in parallel against a **fixed scored-record schema** agreed in the
first two hours ([JSON_CONTRACT.md](JSON_CONTRACT.md)). The UI builds against stub data matching that
shape while the detector is still being tuned; when the real engine lands, it drops in behind the
same shape.

v2 extends the frozen v1 contract **additively — new optional fields only**, so nothing breaks:

| addition | type | meaning |
|---|---|---|
| `cardholder_country` | string | card's home country |
| `ai_summary` | string \| null | cached Gemini reviewer narrative |
| `decision` | `RoutingDecision` | `{action, notify, trail[], used_ai, reason}` |
| `notified` | boolean | whether an analyst alert fired |

New definitions `RoutingDecision` and `Notification` join the schema, and `EdgeType` gains
`"transaction"` (the faint card→merchant backbone edge `build_graph` already emits). All mirrored in
`contract/scored_record.schema.json`, `detector/schema.py`, and `web/src/types.ts`.
