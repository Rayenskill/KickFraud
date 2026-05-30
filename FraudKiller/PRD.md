# PRD — Fraud Hunter

## 1. Problem

A human fraud reviewer receives a stream of transactions and must decide, quickly and defensibly,
which are fraudulent. Today that means scanning raw rows with no prioritization, no context, and no
explanation. We are given `transactions.csv` (1,000 rows, 50 cards, ~1 month, ~7% fraud across four
hidden patterns) and must ship a tool that tells the reviewer **what to look at first, why it's
suspicious, and lets them act on it in seconds**.

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

- Trained/opaque ML models — unexplainable and overkill for 1,000 rows.
- Auth, multi-user, roles.
- A database — in-memory state is sufficient for a single session.
- Real-time streaming or ingestion of arbitrary new files.
- Mobile / responsive layout.
- Containerization (Docker), deployment infra.

Rationale for each is recorded in `IMPLEMENTATION_PLAN.md`.

## 4. Users & primary use case

**Primary user: the fraud reviewer.** Sits down with a queue of flagged transactions, works
highest-risk first, and for each one decides **approve** (it's fraud / take action), **dismiss**
(false positive), or **escalate** (needs a second look). They want context and speed, not a
spreadsheet.

**Core loop:**
1. Open the tool → queue is pre-sorted by score, highest first.
2. Read the top flag: amount vs the card's normal spend, the ranked reasons, recent history.
3. Press `A` / `D` / `E`. The decision is logged and the queue auto-advances.
4. Occasionally: open the ring graph to understand a coordinated cluster, or adjust the cost slider.

## 5. Functional requirements

### Detection
- **FR-D1** Process all 1,000 rows; produce a score and label for every row.
- **FR-D2** Score = sum of independent weighted signals; label = `fraud` if score ≥ threshold.
- **FR-D3** Each fired signal emits a human-readable reason string.
- **FR-D4** Detect P1–P4 (see `DETECTION.md`).
- **FR-D5** Avoid the geo-mismatch and foreign-country traps (require combined deviations).
- **FR-D6** Export `transactions_flagged.csv` with `is_fraud`, `fraud_score`, `fraud_reasons`.

### Reviewer experience
- **FR-R1** Queue presents one flag at a time, sorted by score descending.
- **FR-R2** Single-screen context: amount vs card median, ranked reasons, card recent history,
  mini ring snippet.
- **FR-R3** Keyboard: `A` approve, `D` dismiss, `E` escalate, `J/K` or `←/→` navigate, `U` undo,
  `/` focus search. Decision auto-advances.
- **FR-R4** Undo (stack-based) with toast confirmation on every decision.
- **FR-R5** Search / filter by card, merchant, category, reason, score range, date; sort by score.
- **FR-R6** Cost-aware slider (FP $ vs FN $) re-labels live and shows the count delta.
- **FR-R7** In-session feedback loop: dismissing suppresses similar flags and nudges that signal's
  weight down for the session.
- **FR-R8** Audit log records every decision (who/when/what/reason).

### Graph
- **FR-G1** Force-directed graph; nodes = cards + suspicious merchants; edges = shared IP, shared
  device, co-burst.
- **FR-G2** The QuickPay-Online bursts (May 5 + May 17) render as visible hubs.
- **FR-G3** Click a node → filter the queue to its transactions.

## 6. Success metrics

- Detection F1 ≥ 0.85 against the privately-known fraud band (validation aid only).
- A reviewer can clear a flag in < 5 seconds keyboard-only.
- Ring graph renders the QuickPay hub legibly within the 7-minute demo.
- One-command run succeeds from a clean clone on a fresh machine.

## 7. Demo narrative (7 min)

Load queue → explain one flag's reasons → open ring graph, the two QuickPay rings appear → dismiss a flag
and watch similar flags get suppressed → move the cost slider and watch the flagged count change.
Full script in `DEMO_SCRIPT.md`.
