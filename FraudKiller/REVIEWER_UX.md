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
- **AI summary (v2):** a lazy Gemini risk narrative + a decision-tree routing chip — see below.

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
fast keyboard triage safe: mistakes are one keystroke from reversed. The undo stack stays
session-scoped (in memory); review decisions themselves write through to Mongo — see
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## Search / filter / sort
`Filters.tsx` is a compact **control panel** above the queue. Three always-visible controls in the
top row, an optional advanced grid, and the cost slider:

- **Search box** — one field. Plain text matches `merchant` (substring); a value starting with
  `card_` switches to a `card_id` match. Focus with `/`.
- **Sort dropdown** — `score_desc` (default), `score_asc`, `amount_desc`, `amount_asc`, `date_desc`
  (Newest), `date_asc` (Oldest).
- **Filters toggle** — opens/collapses the advanced grid; shows the active-filter count as a badge.

### Advanced grid
A collapsible grid of structured filters; an empty field clears that constraint. All of these map
1:1 to `GET /transactions` params (served from the in-memory cache, so filtering is instant — no
per-keystroke Atlas round-trip):

| Control | Param | Notes |
|---|---|---|
| Category | `category` | grocery, gas, restaurant, online_retail, … |
| Channel | `channel` | online / in_person / atm |
| Status | `status` | pending / approved / dismissed / escalated |
| Signal fired | `reason` | e.g. show everything that fired `merchant_burst_cross_card` |
| Min / Max score | `min_score` / `max_score` | 0–1, step 0.05 |
| Min / Max amount | `min_amount` / `max_amount` | dollars |
| From / To date | `date_from` / `date_to` | ISO dates |

Useful both for targeted review and for the demo ("filter to the QuickPay cluster"). A **Clear
Filters** button appears whenever any constraint is set.

---

## AI summary
On the open flag, `AiSummary.tsx` renders a **lazy Gemini panel** plus a **decision-tree routing
chip**.

- **Gemini summary** — fetched on demand from `GET /transaction/{id}/summary`
  → `{transaction_id, summary, enabled}`. A 1–2 sentence plain-language risk narrative with a
  recommended action. The server **caches per `transaction_id` and persists it as `ai_summary`**, so
  navigation is cheap after the first view. If Gemini is disabled (no `GEMINI_API_KEY`), the endpoint
  returns `enabled: false` and the panel hides itself — rules and UI degrade gracefully.
- **Routing chip** — reads `record.decision` (the contract-v2 `RoutingDecision`) and renders the
  decision-tree outcome: `auto clear` / `queue` / `escalate`, appending **"· analyst notified"** when
  `decision.notify` is true.

The chip and the queue's *presence* are independent: the decision tree (`detector/decision_tree.py`,
pure) routes every record; the queue holds the ones a human must see. See [DETECTION.md](DETECTION.md)
for branch order and [JSON_CONTRACT.md](JSON_CONTRACT.md) for the `RoutingDecision` shape.

---

## Simulate incoming transaction
`IngestForm.tsx` is a collapsible **"Simulate incoming transaction"** panel that demonstrates the
v2 ingest pipeline end-to-end: score → decision tree → notification. Three presets seed the form, then
**Add transaction** POSTs to `/transactions` and returns `{record, decision, notification}`.

| Preset | What it sends | Expected route |
|---|---|---|
| **Ring burst** | >$200 QuickPay charge inside the May-17 cross-card burst window | `escalate` · analyst notified (completes the ring → critical signal) |
| **Bust-out** | $1,850 electronics charge on a low-median card | `escalate` · analyst notified (trips `amount_vs_card_median`) |
| **Clear** | benign $12.50 grocery/restaurant run | `auto_clear`, no notification |

The result panel shows the routing action, `fraud_score`, the decision `reason`, and the full
**`trail[]`** of branch steps. **"· analyst notified ✉️"** appears when a notification was created. A
toast mirrors the outcome. Notifications are **LOG/QUEUE ONLY** — recorded to the `notifications`
collection + audit log (`sent: false`); nothing is actually emailed. See
[API.md](API.md) for the ingest endpoint and [DATABASE.md](DATABASE.md) for the notifications model.

---

## Cost-aware slider
A slider expresses the **FP $ vs FN $** trade-off. Sliding it re-labels the queue **live** and shows
the count delta ("flags 71 → 58"). Because scores are fixed and only the threshold moves, this is
instant — and the relabel is **cache-only** (not persisted; scores never change). It makes the
precision/recall trade-off tangible to a non-technical reviewer.

---

## In-session feedback loop (the "watch it learn" beat)
When a reviewer **dismisses** a flag, the tool:
1. **Suppresses similar flags** — same card+reason, or the same merchant-burst cluster — so the
   reviewer isn't asked the same question 16 times.
2. **Nudges that signal's weight down** for the session, so comparable future flags score lower.
3. **Records it in the audit log** (who / when / what / which reason).

The effect is visible during the demo: dismiss one QuickPay flag and watch related flags drop out of
the queue and the count fall. It demonstrates "learning" without any opaque model. Suppression and
session weight overrides stay in memory (session-scoped); only the review decision persists.

---

## Audit log
Every decision is appended to an **audit trail** — reviewer, decision, the exact reason text shown at
decision time, and timestamp. v2 also records **non-human (decision-tree) entries** via
`system_event()`, so auto-clears and escalations are auditable too. The trail persists to the Mongo
`audit` collection and is loaded at startup. This is both a bonus deliverable and the backbone of the
feedback-loop demo. Viewable via the UI and `GET /audit`.

---

## Performance
All 1,000 rows live in memory (the cache loaded at startup; Mongo is the source of truth). The list
is **virtualized**; interactions are instant. Filtering and sorting hit the cache, not Atlas. No
spinner between decisions — the next flag is already there.

---

## Acceptance checks
- Drive the entire queue **keyboard-only**: approve/dismiss/escalate/undo without touching the mouse.
- Dismiss a flag → confirm similar flags are suppressed and the count drops.
- Confirm the dismissal appears in the audit log with its reason.
- Move the cost slider → confirm the flagged count changes live.
- Click a node in the ring graph → confirm the queue filters to that node's transactions.
- Open a flag → confirm the AI summary + routing chip render (or the panel hides with no key).
- Run the **Bust-out** ingest preset → confirm it escalates and shows "analyst notified"; run
  **Clear** → confirm it auto-clears with no notification.
