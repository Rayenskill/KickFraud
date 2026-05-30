# ARCHITECTURE

## Module map

```
fraud-hunter/
├─ detector/                pure-Python detection engine (no web deps)
│  ├─ baselines.py          per-card profiles: median/MAD amount, categories, country, channels,
│  │                        devices/IPs, hour-of-day
│  ├─ aggregates.py         cross-card maps: (merchant,day) distinct-card counts + amount stats,
│  │                        IP→cards, device→cards, rolling per-card velocity windows
│  ├─ signals.py            one function per signal + weight constants + reason strings
│  ├─ score.py              orchestrates: csv → scored records + graph edges + flagged csv
│  └─ io.py                 load csv, write transactions_flagged.csv
├─ api/                     FastAPI
│  ├─ main.py               endpoints; loads CSV once at startup, scores once, holds in memory
│  └─ state.py              in-session review decisions + feedback-loop weight overrides + audit log
├─ web/                     React + Vite + TypeScript
│  ├─ ReviewQueue.tsx       one-card-at-a-time triage, keyboard-driven, undo
│  ├─ RingGraph.tsx         force-directed fraud-ring graph (signature feature)
│  ├─ Filters.tsx           search / filter / cost slider
│  └─ api.ts                typed client for the API
├─ tests/                   pytest: known-fraud + known-legit cases per pattern
├─ data/transactions.csv
├─ transactions_flagged.csv generated deliverable
├─ docs/                    README · PRD · IMPLEMENTATION_PLAN · HYPOTHESES · deep dives
└─ run.sh / run.ps1         one-command: build detector output, start API + web
```

## Data flow

```
                      startup
                         │
   data/transactions.csv ─▶ detector.score()  ── runs ONCE ──┐
                         │                                    │
                         ▼                                    ▼
              transactions_flagged.csv          in-memory: scored records
                  (deliverable)                  + graph edges
                                                 + mutable review-state map (state.py)
                                                       │
                          ┌────────────────────────────┼──────────────────────────┐
                          ▼                             ▼                          ▼
                   GET /transactions             GET /graph              POST /review /undo
                   GET /transaction/{id}                                 POST /threshold
                          │                             │                          │
                          └──────────────── React (web/) ───────────────────────────┘
                                ReviewQueue · RingGraph · Filters
```

1. **Startup:** API loads the CSV, runs `detector.score()` exactly once, and keeps the scored
   records, graph edges, and a mutable review-state map in memory. No database.
2. **Read:** React fetches `/transactions` (scored + reasons, filterable/sortable) and `/graph`.
3. **Act:** React posts decisions to `/review/{id}`; the API updates state, applies the feedback
   loop, and appends to the audit log.
4. **Tune:** React posts a cost ratio to `/threshold`; the API re-labels in place (scores are fixed,
   only the cutoff moves) and returns the new counts.
5. **Export:** `/export` streams `transactions_flagged.csv`.

## Why in-memory, single batch score

1,000 rows fit trivially in memory; scoring once at startup keeps every interaction instant and
removes a whole class of consistency bugs. The cost slider never re-scores — it only moves the
threshold over fixed scores — so it's O(rows) and feels live. See `IMPLEMENTATION_PLAN.md` for the
full "what we skip and why" rationale.

## The JSON contract is the spine

The detector and the UI are built in parallel against a **fixed scored-record schema** agreed in the
first two hours (`JSON_CONTRACT.md`). The UI builds against stub data matching that schema while the
detector is still being tuned; when the real engine lands, it drops in behind the same shape.
