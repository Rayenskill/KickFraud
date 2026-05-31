# TEAM_SPLIT — 3 people, 3 Claude subscriptions + 1 Codex subscription

You have **three people**, **three Claude subscriptions** (one each), and **one extra Codex
subscription** (a fourth agent seat). The cleanest way to think about it: three humans own three
tracks, each drives a Claude agent on their track, and the spare Codex is a **fourth worker** parked
on the most parallelizable, self-contained work so it runs in the background without creating merge
chaos.

The three tracks map exactly to the three seams in the architecture, which barely touch each other
once the JSON contract is frozen.

---

## The split

| Track | Human | Primary agent | Owns |
|---|---|---|---|
| **A — Detection** | Dev A | Claude #1 | `detector/` (baselines, aggregates, signals, score, io), threshold tuning, `transactions_flagged.csv`, detection tests, `HYPOTHESES.md`, `DETECTION.md` |
| **B — Reviewer UI** | Dev B | Claude #2 | `web/` queue, keyboard nav, undo, filters, cost slider, feedback-loop UI, `REVIEWER_UX.md` |
| **C — Graph + API + glue** | Dev C | Claude #3 | FastAPI endpoints, `state.py`, audit log, `RingGraph.tsx`, `run.sh`/`run.ps1`, `README`/`PRD`/`IMPLEMENTATION_PLAN` |

### Pipeline & data (v2) — Track C or the spare seat
v2 adds a persistence + AI + ingestion seam that bolts onto the contract additively. It's
spec-complete (see the v2 ground truth), so it slots onto **Track C** (it's the API/glue track) or
gets handed to the **4th seat** when Track C is on the critical path. One owner per file regardless.

| Area | Files | Notes |
|---|---|---|
| **MongoDB persistence** | `api/db.py`, `api/config.py`, `scripts/seed_mongo.py` | Sync pymongo wrapper; Atlas via `MONGO_URI`. Mongo is source of truth; reads serve from an in-memory cache, writes write through. `is_connected()` falls back to CSV in-memory if `MONGO_URI` unset/unreachable. Seed is idempotent (`python -m scripts.seed_mongo`). |
| **Decision tree** | `detector/decision_tree.py` | **PURE — no web/db/network** (stays on the Track A rule: detector core is reusable + unit-testable). `route()` → `auto_clear`/`queue`/`escalate`; `notify==True` triggers the analyst alert. |
| **Gemini AI** | `api/gemini.py` | `summarize()` (reviewer narrative, cached + persisted as `ai_summary`) and `classify()` (tie-breaker verdict on borderline scores). Returns `None` with no key / SDK missing / call fail → rules + UI degrade. |
| **Notifications** | `api/notifications.py` | `notify_analyst()` builds a notification doc. Default transport `"log"` records only (`sent=False`) — **never sends**. `_send()` is the single pluggable SMTP/API seam (stub). |
| **Ingestion** | `api/ingest.py` | `normalize_row` → `score_new` → `decide` (calls `gemini.classify` then `route()` only on the borderline+non-critical branch; pure `route()` otherwise). Feeds `POST /transactions`. |

`detector/score.py` is **refactored** (extracts `score_row` so a single live txn can be scored,
`build_graph` tolerant of dict records) — owned by **Track A**. `api/state.py` now **writes through**
to Mongo (`review_status`, audit insert/delete; `system_event()` for decision-tree audit entries) —
owned by **Track C**. Contract v2 (additive optional fields: `cardholder_country`, `ai_summary`,
`decision`, `notified`) is mirrored in `contract/scored_record.schema.json`, `detector/schema.py`,
and `web/src/types.ts` — co-owned, frozen first like v1.

UI for the new seam lives on **Track B**: `Filters.tsx` (search + sort + advanced grid + cost
slider), `AiSummary.tsx` (lazy Gemini panel + decision-tree routing chip), `IngestForm.tsx`
("Simulate incoming transaction" presets). All wired in `App.tsx`.

### Where the 4th seat (Codex) goes
Give Codex to **whoever is on the critical path at the moment**, but its standing assignment is the
**mechanical, well-specified, low-merge-risk work** that doesn't need a human babysitting it:

- **Test scaffolding** — generate the per-pattern pytest cases and the precision/recall harness from
  `TESTING.md` (the spec is already written; it's near-mechanical). In v2 this extends to
  `tests/test_decision_tree.py` (every branch), `tests/test_ingest.py`, `tests/test_gemini_fallback.py`,
  and `tests/test_db_mongomock.py` — all hermetic (run with **no secrets**, mongomock for DB).
- **The flagged-CSV exporter** (`detector/io.py` write path) — fully specified by `JSON_CONTRACT.md`.
- **`run.sh` / `run.ps1`** — boilerplate one-command scripts for two platforms (v2: also runs
  `python -m scripts.seed_mongo`, which skips gracefully without `MONGO_URI`).
- **Stub data** (`web/src/stub/transactions.stub.json`) — one record per pattern in the frozen shape.
- **Boilerplate endpoints** — the CRUD-shaped parts of the API (`/transactions`, `/transaction/{id}`,
  `/export`) where the contract leaves little to interpret. v2: `/notifications`,
  `/transaction/{id}/summary`, and the `scripts/seed_mongo.py` loader are equally spec-complete.

Rule of thumb: **Claude on the reasoning-heavy work** (signal design, UX behavior, the graph, tuning
judgment, decision-tree thresholds), **Codex on the spec-complete boilerplate** that can run
semi-autonomously while the human on that track does the thinking-heavy part. Codex commits to its
own branch; the track owner reviews and merges.

---

## Why this division works
- The three tracks share **one interface only**: the JSON contract. Freeze it first (H0–H2) and the
  three humans never block each other. Contract v2 stays additive (new optional fields only) so the
  freeze still holds.
- Each human owns a vertical slice end-to-end, so there's a clear "who decides" for every file.
- The 4th agent is additive, not a coordination tax: it only touches files that are fully specified
  by docs already written, on its own branch.
- The new pipeline keeps the seams clean: pure detector (decision tree included), DB + network in
  `api/`, presentation in `web/`. Mongo is the source of truth; the in-memory cache keeps reads fast.

---

## Hour-by-hour with four agents

| Window | Dev A (Claude #1) | Dev B (Claude #2) | Dev C (Claude #3) | Codex (4th seat) |
|---|---|---|---|---|
| **H0–H2** | Co-author + freeze `JSON_CONTRACT.md` (incl. contract v2 fields); scaffold `detector/` | Co-author contract; scaffold `web/` | Co-author contract; scaffold `api/` + repo skeleton; `.env.example` | Generate **stub data** + `run.sh`/`run.ps1` skeletons from the contract |
| **H2–H10** | baselines → aggregates → signals → score; extract `score_row`; **`decision_tree.py`** (pure) | queue + keyboard nav + detail pane vs stub | boilerplate endpoints; `config.py` + `db.py` Mongo wrapper | **test scaffolding** + `detector/io.py` CSV exporter |
| **H10–H14** | tuning hooks, reason strings, decision-tree thresholds | `Filters.tsx`, cost slider, `IngestForm.tsx` | `/graph` + `RingGraph.tsx`, `state.py` write-through, audit log; `ingest.py` + `gemini.py` + `notifications.py` | fill out remaining endpoints (`/undo`, `/audit`, `/export`, `/notifications`, `/summary`); `seed_mongo.py` |
| **H14–H18** | **tune weights/threshold to F1 ≥ 0.85**; detection + decision-tree tests | polish UX, `AiSummary.tsx`, wire to real API | integrate all three; startup cache/seed/fallback; `README`/`PRD`/`IMPL` | run full `pytest` (29) hermetic, fix flaky/boilerplate gaps |
| **H18–H24** | verify CSV deliverable; clean scratch files | demo polish | demo wiring; `run` scripts + seed end-to-end test | regenerate stub→real diffs; final lint/cleanup pass |

> If a track finishes early, that human points **their** Claude at the integration seam (H14 is the
> crunch) and Codex keeps grinding tests and cleanup.

---

## Coordination rules
1. **Contract first.** Nothing real gets built before `JSON_CONTRACT.md` is frozen. Stub data matches
   it exactly. Contract v2 extends it **additively** (optional fields only) — no breaking edits.
2. **One owner per file.** Branches per track; Codex on its own branch. The track owner reviews
   anything an agent wrote before merge. The v2 pipeline files (`db.py`, `gemini.py`,
   `notifications.py`, `ingest.py`, `seed_mongo.py`) sit under one owner — Track C or the spare seat.
3. **Detector stays web-free *and* db-free.** Track A's code — including `detector/decision_tree.py` —
   imports nothing from `api/` or `web/`. DB + network code lives in `api/`. It's the reusable,
   testable core.
4. **Re-run `pytest` after every tune.** Especially before merging detection changes (guards the
   traps). Tests are hermetic — they run with **no secrets** (mongomock + Gemini-off fallback).
5. **Daylight the integration at H14.** Don't leave UI↔API↔detector wiring to the final hours.

---

## If you only had 2 people instead of 3
Merge **Track C into A and B**: Dev A takes API + glue alongside detection; Dev B takes the graph
alongside the UI. The 4th Codex seat then matters even more — it absorbs the entire "glue" surface
(run scripts, tests, exporter, stub, boilerplate endpoints, the **Mongo/seed/notifications pipeline**,
docs) so two humans can stay on detection and reviewer experience, the two 40-point tracks.
