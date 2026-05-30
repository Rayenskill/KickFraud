# REVIEWER_UX — the review experience in depth

Reviewer experience is **40 of 100 points** — equal to detection. The guiding idea: a reviewer
shouldn't read a spreadsheet, they should be handed one decision at a time with everything they need
to make it, and act in seconds.

---

## The queue, not a table
Flagged transactions are presented **one at a time, highest score first**. The whole screen is about
the current flag; there is no grid to scan. Behind it, a virtualized list holds all flags so
navigation is instant across 1,000 rows.

### Single-screen context (everything to decide on one card)
- **Headline:** amount, merchant, card, timestamp.
- **Amount vs card median:** a visual showing how far this sits from the card's normal spend (e.g.
  "$835 — 46× this card's median of $18").
- **Ranked reasons:** the plain-language reason list from the detector, most important first.
- **Card recent history:** the card's last several transactions for context.
- **Mini ring snippet:** a small cutout of the fraud-ring graph centered on this card/merchant, so
  coordinated context is visible without leaving the queue.

---

## Keyboard-first
The reviewer never needs the mouse.

| Key | Action |
|---|---|
| `A` | approve (it's fraud / take action) |
| `D` | dismiss (false positive) |
| `E` | escalate (needs a second look) |
| `J` / `K` or `←` / `→` | navigate prev/next |
| `U` | undo |
| `/` | focus search |

- A decision **auto-advances** to the next flag.
- A **footer legend** of the shortcuts is always visible.

---

## Undo + toasts
Every decision pops a **toast** confirmation ("Dismissed tx_000992 — undo (U)"). **Undo is
stack-based**, so the reviewer can walk back multiple decisions, not just the last one. This makes
fast keyboard triage safe: mistakes are one keystroke from reversed.

---

## Search / filter / sort
Filter by card, merchant, category, **reason** (e.g. show me everything that fired
`merchant_burst_cross_card`), score range, and date. Sort by score. Useful both for targeted review
and for the demo ("filter to the QuickPay cluster").

---

## Cost-aware slider
A slider expresses the **FP $ vs FN $** trade-off. Sliding it re-labels the queue **live** and shows
the count delta ("flags 71 → 58"). Because scores are fixed and only the threshold moves, this is
instant. It makes the precision/recall trade-off tangible to a non-technical reviewer.

---

## In-session feedback loop (the "watch it learn" beat)
When a reviewer **dismisses** a flag, the tool:
1. **Suppresses similar flags** — same card+reason, or the same merchant-burst cluster — so the
   reviewer isn't asked the same question 16 times.
2. **Nudges that signal's weight down** for the session, so comparable future flags score lower.
3. **Records it in the audit log** (who / when / what / which reason).

The effect is visible during the demo: dismiss one QuickPay flag and watch related flags drop out of
the queue and the count fall. It demonstrates "learning" without any opaque model.

---

## Audit log
Every decision is appended to an **audit trail** — reviewer, decision, the exact reason text shown at
decision time, and timestamp. This is both a bonus deliverable and the backbone of the feedback-loop
demo. Viewable via the UI and `GET /audit`.

---

## Performance
All 1,000 rows live in memory. The list is **virtualized**; interactions are instant. No spinner
between decisions — the next flag is already there.

---

## Acceptance checks
- Drive the entire queue **keyboard-only**: approve/dismiss/escalate/undo without touching the mouse.
- Dismiss a flag → confirm similar flags are suppressed and the count drops.
- Confirm the dismissal appears in the audit log with its reason.
- Move the cost slider → confirm the flagged count changes live.
- Click a node in the ring graph → confirm the queue filters to that node's transactions.
