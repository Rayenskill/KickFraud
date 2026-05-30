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

### Where the 4th seat (Codex) goes
Give Codex to **whoever is on the critical path at the moment**, but its standing assignment is the
**mechanical, well-specified, low-merge-risk work** that doesn't need a human babysitting it:

- **Test scaffolding** — generate the per-pattern pytest cases and the precision/recall harness from
  `TESTING.md` (the spec is already written; it's near-mechanical).
- **The flagged-CSV exporter** (`detector/io.py` write path) — fully specified by `JSON_CONTRACT.md`.
- **`run.sh` / `run.ps1`** — boilerplate one-command scripts for two platforms.
- **Stub data** (`web/src/stub/transactions.stub.json`) — one record per pattern in the frozen shape.
- **Boilerplate endpoints** — the CRUD-shaped parts of the API (`/transactions`, `/transaction/{id}`,
  `/export`) where the contract leaves little to interpret.

Rule of thumb: **Claude on the reasoning-heavy work** (signal design, UX behavior, the graph, tuning
judgment), **Codex on the spec-complete boilerplate** that can run semi-autonomously while the human
on that track does the thinking-heavy part. Codex commits to its own branch; the track owner reviews
and merges.

---

## Why this division works
- The three tracks share **one interface only**: the JSON contract. Freeze it first (H0–H2) and the
  three humans never block each other.
- Each human owns a vertical slice end-to-end, so there's a clear "who decides" for every file.
- The 4th agent is additive, not a coordination tax: it only touches files that are fully specified
  by docs already written, on its own branch.

---

## Hour-by-hour with four agents

| Window | Dev A (Claude #1) | Dev B (Claude #2) | Dev C (Claude #3) | Codex (4th seat) |
|---|---|---|---|---|
| **H0–H2** | Co-author + freeze `JSON_CONTRACT.md`; scaffold `detector/` | Co-author contract; scaffold `web/` | Co-author contract; scaffold `api/` + repo skeleton | Generate **stub data** + `run.sh`/`run.ps1` skeletons from the contract |
| **H2–H10** | baselines → aggregates → signals → score | queue + keyboard nav + detail pane vs stub | boilerplate endpoints (`/transactions`, `/transaction/{id}`) | **test scaffolding** + `detector/io.py` CSV exporter |
| **H10–H14** | tuning hooks, reason strings | feedback-loop UI, cost slider | `/graph` + `RingGraph.tsx`, `state.py`, audit log | fill out remaining endpoints (`/undo`, `/audit`, `/export`) |
| **H14–H18** | **tune weights/threshold to F1 ≥ 0.85**; detection tests | polish UX, wire to real API | integrate all three; `README`/`PRD`/`IMPL` | run full `pytest`, fix flaky/boilerplate test gaps |
| **H18–H24** | verify CSV deliverable; clean scratch files | demo polish | demo wiring; `run` scripts end-to-end test | regenerate stub→real diffs; final lint/cleanup pass |

> If a track finishes early, that human points **their** Claude at the integration seam (H14 is the
> crunch) and Codex keeps grinding tests and cleanup.

---

## Coordination rules
1. **Contract first.** Nothing real gets built before `JSON_CONTRACT.md` is frozen. Stub data matches
   it exactly.
2. **One owner per file.** Branches per track; Codex on its own branch. The track owner reviews
   anything an agent wrote before merge.
3. **Detector stays web-free.** Track A's code imports nothing from `api/` or `web/` — it's the
   reusable, testable core.
4. **Re-run `pytest` after every tune.** Especially before merging detection changes (guards the
   traps).
5. **Daylight the integration at H14.** Don't leave UI↔API↔detector wiring to the final hours.

---

## If you only had 2 people instead of 3
Merge **Track C into A and B**: Dev A takes API + glue alongside detection; Dev B takes the graph
alongside the UI. The 4th Codex seat then matters even more — it absorbs the entire "glue" surface
(run scripts, tests, exporter, stub, boilerplate endpoints, docs) so two humans can stay on detection
and reviewer experience, the two 40-point tracks.
