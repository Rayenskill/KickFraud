# DEMO_SCRIPT — the 8-minute run

The tool is only as good as the pitch. Script it, rehearse it, time it. Six beats. v2 adds a
live-ingestion beat that lands a transaction in front of you and lets the decision tree escalate
it on stage — see [API.md](API.md) for the endpoints and [ARCHITECTURE.md](ARCHITECTURE.md) for
the pipeline.

---

## Beat 0 — One-line framing (0:00–0:30)
"A reviewer gets a stream of transactions with no prioritization and no explanation. We built a
triage tool that tells them what to look at first, why it's suspicious, and lets them act in seconds
— with a graph that exposes coordinated attacks you can't see one transaction at a time."

## Beat 1 — The queue + a reason (0:30–2:00)
- Open the tool. Queue is pre-sorted, highest score first.
- Land on a high-score flag (a gift-card bust-out, P3). Read the ranked reasons aloud:
  *"$735 is 30× this card's median; gift_card never seen on this card."*
- Point out: **every flag is explainable — no black box.** Show the amount-vs-median visual and the
  card's recent history on the same screen.
- Open the **AI summary panel** (`AiSummary.tsx`) — a 1–2 sentence Gemini risk narrative + recommended
  action, lazily fetched from `GET /transaction/{id}/summary` and cached. "Plain language on top of the
  rules — and if there's no API key, the panel degrades cleanly to rules-only." Note the **decision-tree
  routing chip** showing the action (auto_clear / queue / escalate).
- Drop into the **filter/sort panel** (`Filters.tsx`): search box + sort dropdown + a collapsible
  advanced grid (category, channel, status, signal-fired, min/max score, min/max amount, from/to date).
  "Reviewer slices the queue any way they need — all served from cache, no per-keystroke round-trip."

## Beat 2 — Live ingestion (the decision tree fires) (2:00–3:30)
- Open **"Simulate incoming transaction"** (`IngestForm.tsx`) and click the **Ring burst** preset.
  It posts a **>$200 QuickPay Online charge** (`card_999`, $350, `2026-05-17T14:30:00`) straight into
  the **May-17 coordinated burst window** via `POST /transactions`.
- The ingest pipeline rebuilds baselines + aggregates over all rows **including the new one**, scores it,
  and routes it through the **decision tree**. The new charge completes the cross-card ring, so the
  **`merchant_burst_cross_card` critical signal** fires — branch (1), **auto-escalate**.

  | preset | what it trips | action | notify |
  |---|---|---|---|
  | **Ring burst** | `merchant_burst_cross_card` critical signal (May-17 window) | escalate | yes |
  | Bust-out | `amount_vs_card_median` critical signal | escalate | yes |
  | Clear | benign grocery run, score < 0.42 | auto_clear | no |

- Watch the **toast**: *"Ingested tx_live_… → escalate · analyst notified."* The response carries
  `{record, decision, notification}` and the new flag drops into the queue.
- "No human routed this — the **business-logic decision tree** did, the moment the charge landed."

## Beat 3 — The analyst gets notified (3:30–4:15)
- Pull up notifications (`GET /notifications`, newest-first). There's the escalation: the
  notification doc `{notification_id, transaction_id, to, subject, body, action, score, transport, sent}`.
- "Escalations are **logged/queued, never emailed** — `transport: log`, `sent: false`. There's a single
  pluggable seam for SMTP or an email API later; the audit log records the same event as a system entry."
- This is the whole loop on stage: live charge → critical signal → escalate → analyst alerted.

## Beat 4 — Keyboard triage (4:15–5:00)
- Decide a few flags by keyboard only: `A`, `D`, `E`. Note the auto-advance and the toast.
- Hit `U` to undo. "Fast, and safe — undo is a stack."

## Beat 5 — The ring graph (the wow) (5:00–6:15)
- Open the ring graph. **Two QuickPay Online hubs** appear: the **May 5 burst (6 cards)** and the
  **May 17 burst (7 cards)**, each a merchant node with cards radiating off it — and **card_037
  bridging both** rings. The charge you just ingested in beat 2 sits on the May-17 hub.
- "No single one of these cards looks unusual on its own. The fraud only exists **across** cards —
  here are two coordinated bursts in one glance, and that card in the middle shows up in both."
- Click the QuickPay node → the queue filters to those coordinated >$200 flags.

## Beat 6 — Watch it learn, then the cost slider (6:15–8:00)
- Dismiss one QuickPay flag. Watch **similar flags get suppressed** and the count drop.
  "Dismissing a false positive teaches the session: it suppresses similar flags and nudges that
  signal down — and every decision lands in the audit log." Show the audit entry.
- Move the **cost slider** toward "false negatives are expensive." Flag count rises live; toward
  "false positives are expensive," it falls. "The reviewer tunes the precision/recall trade-off in
  business terms, instantly — a **cache-only relabel**; the underlying scores never change."
- Close: "Grounded detection of four real patterns, an explainable reason **and an AI summary** for
  every flag, a decision tree that escalates live charges and alerts the analyst, a fast keyboard
  workflow, and a graph that makes coordinated fraud visible. One command to run, tested per pattern."

---

## Rehearsal checklist
- [ ] Time it — under 8:00 with breathing room.
- [ ] Pre-load the browser to the queue so beat 1 is instant.
- [ ] Know which transaction id you'll open in beat 1 (a clean P3 example).
- [ ] Confirm the **Ring burst** preset escalates + notifies before you present (run it once, then
      reset state). Have the notifications view one click away for beat 3.
- [ ] Decide whether to demo **with** a `GEMINI_API_KEY` (live summaries) or rules-only — both work;
      mention the graceful fallback either way.
- [ ] Confirm both QuickPay hubs (May 5 + May 17) are visually obvious before you present.
- [ ] Have the audit log view one click away for beat 6.
- [ ] Decide who speaks which beat if presenting as a team.
