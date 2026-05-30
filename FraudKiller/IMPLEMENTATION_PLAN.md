# IMPLEMENTATION_PLAN

## Stack (locked)
- **Detection + API:** Python, FastAPI. Detector is pure Python with no web deps so it's testable in
  isolation and reusable.
- **UI:** React + Vite + TypeScript.
- **State:** in-memory, session-scoped. No database.

## Sequencing (24h)

| Window | Work |
|---|---|
| **H0–H2** | Agree and **freeze the JSON contract** (`JSON_CONTRACT.md`). Scaffold all three trees (`detector/`, `api/`, `web/`). Create stub data matching the contract so UI and detector proceed in parallel. |
| **H2–H10** | **Detection and UI in parallel.** Detector: baselines → aggregates → signals → score → flagged CSV. UI: review queue against stub data, keyboard nav, detail pane. |
| **H10–H14** | **Graph + feedback loop + cost slider.** `/graph` endpoint + RingGraph.tsx; dismissal suppression + session weights; threshold endpoint + slider. |
| **H14–H18** | **Tuning + tests + docs.** Tune weights/threshold to F1 ≥ 0.85 against the private fraud band; per-pattern pytest; finish README/PRD/HYPOTHESES. |
| **H18–H24** | **Polish, demo script, buffer.** Rehearse the 7-min demo, fix rough edges, clean scratch files. |

The H0–H2 contract freeze is the linchpin: it's what lets two or three people build simultaneously
without blocking each other.

## What we build
- `detector/` engine with one function per signal, weights as top-of-module constants.
- FastAPI app: `/transactions`, `/transaction/{id}`, `/review/{id}`, `/undo`, `/graph`,
  `/threshold`, `/audit`, `/export`.
- React queue + ring graph + filters/slider.
- `tests/` with known-fraud + known-legit per pattern.
- `run.sh` / `run.ps1` one-command run.
- Docs (this set).

## What we explicitly skip — and why

| Skipped | Why |
|---|---|
| **Trained / opaque ML** | The brief rewards explainability. Additive weighted signals are interpretable and easily tuned; ML is overkill for 1,000 rows and would *lose* points by being a black box. |
| **Auth / multi-user / roles** | Single-reviewer demo. Auth adds zero detection or reviewer-experience value in the judged window. |
| **Database** | 1,000 rows fit in memory. A DB adds setup, migration, and consistency surface area for no benefit in a session-scoped tool. |
| **Real-time streaming / arbitrary file ingestion** | Scope is one known CSV. Streaming is a "with another week" item (README). |
| **Mobile / responsive layout** | Reviewer tool is a desktop workflow; the 7-min demo is on a laptop. |
| **Docker / deploy infra** | One-command local run is the requirement. Containerization is pure overhead here. |

These cuts are deliberate: they protect time for the two things scored highest — detection quality
and reviewer experience — plus the signature graph.

## Definition of done
- All 1,000 rows scored + labeled + reasoned; `transactions_flagged.csv` written.
- Queue drivable keyboard-only with undo; feedback loop + audit log working.
- Ring graph renders the QuickPay hub; node-click filters the queue.
- Cost slider re-labels live.
- `pytest` green (per-pattern fraud above threshold, legit below); F1 ≥ 0.85 on the private band.
- `run.sh` / `run.ps1` works from a clean clone.
- Scratch files (`Downloads\_an*.txt`, `/tmp/*.py`) deleted.
