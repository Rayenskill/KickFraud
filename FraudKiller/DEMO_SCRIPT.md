# DEMO_SCRIPT — the 7-minute run

The tool is only as good as the pitch. Script it, rehearse it, time it. Five beats.

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

## Beat 2 — Keyboard triage (2:00–3:00)
- Decide a few flags by keyboard only: `A`, `D`, `E`. Note the auto-advance and the toast.
- Hit `U` to undo. "Fast, and safe — undo is a stack."

## Beat 3 — The ring graph (the wow) (3:00–4:30)
- Open the ring graph. **Two QuickPay Online hubs** appear: the **May 5 burst (6 cards)** and the
  **May 17 burst (7 cards)**, each a merchant node with cards radiating off it — and **card_037
  bridging both** rings.
- "No single one of these cards looks unusual on its own. The fraud only exists **across** cards —
  here are two coordinated bursts in one glance, and that card in the middle shows up in both."
- Click the QuickPay node → the queue filters to those coordinated >$200 flags.

## Beat 4 — Watch it learn (4:30–5:45)
- Dismiss one QuickPay flag. Watch **similar flags get suppressed** and the count drop.
- "Dismissing a false positive teaches the session: it suppresses similar flags and nudges that
  signal down — and every decision lands in the audit log." Show the audit entry.

## Beat 5 — Cost slider + close (5:45–7:00)
- Move the **cost slider** toward "false negatives are expensive." Flag count rises live; toward
  "false positives are expensive," it falls. "The reviewer tunes the precision/recall trade-off in
  business terms, instantly."
- Close: "Grounded detection of four real patterns, an explainable reason for every flag, a fast
  keyboard workflow, and a graph that makes coordinated fraud visible. One command to run, tested per
  pattern."

---

## Rehearsal checklist
- [ ] Time it — under 7:00 with breathing room.
- [ ] Pre-load the browser to the queue so beat 1 is instant.
- [ ] Know which transaction id you'll open in beat 1 (a clean P3 example).
- [ ] Confirm both QuickPay hubs (May 5 + May 17) are visually obvious before you present.
- [ ] Have the audit log view one click away for beat 4.
- [ ] Decide who speaks which beat if presenting as a team.
