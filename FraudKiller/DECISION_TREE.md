# DECISION_TREE — from a score to an action

The detector produces a **0..1 fraud score + ranked reasons**. That is a *judgement*, not an
*action*. The decision tree is the thin business-logic layer in between: it maps a scored
record to exactly one of three operational outcomes — **auto-clear, queue, or escalate** — and
decides whether to fire an analyst alert. Without it, every flag would land in one undifferentiated
pile and a coordinated ring would look the same as a marginal outlier.

It lives in `detector/decision_tree.py` and is **pure** — no web, no DB, no network. The same
tree runs in batch scoring, in the live-ingestion pipeline (`api/ingest.py`), and is the source
of the diagram below.

---

## Outcomes

| Action | Meaning |
|---|---|
| `auto_clear` | Below the clear threshold — no human time spent. |
| `queue` | Sent to the human review queue (the normal path for a flag). |
| `escalate` | High-confidence / coordinated fraud — `notify=True`, alerts the on-call analyst. |

`notify==True` is **the** trigger for the analyst alert in `api/notifications.py`. Only the two
escalation paths set it; queue and auto-clear never do. See [NOTIFICATIONS.md](NOTIFICATIONS.md).

---

## Config

`DecisionConfig` (tunable, passed to `route()`):

| Field | Default | Role |
|---|---|---|
| `clear_below` | `0.42` | Score below this → auto-clear. Mirrors the detector's default fraud cutoff. |
| `escalate_at` | `0.80` | Score at/above this → escalate. |
| `critical_signals` | `{merchant_burst_cross_card, amount_vs_card_median}` | Fire these and you escalate **regardless of score**. |

The critical signals escalate on their own because a coordinated cross-card ring (P4,
`merchant_burst_cross_card`) or an extreme amount outlier (P3, `amount_vs_card_median`) is
operationally urgent even when the normalized score sits in the middle band.

---

## The tree — `route(record, ai_verdict=None, config)`

Branches are evaluated top to bottom; **first match wins**.

```
            ┌─────────────────────────────────────────────┐
            │  scored record (fraud_score, reasons[])      │
            └───────────────────────┬─────────────────────┘
                                    ▼
       ┌──────────────────────────────────────────────────────┐
  (1)  │ a critical signal fired?                              │── yes ──▶ ESCALATE  notify=True
       │ (merchant_burst_cross_card | amount_vs_card_median)   │
       └───────────────────────┬──────────────────────────────┘
                              no
                                ▼
       ┌──────────────────────────────────────────────────────┐
  (2)  │ score >= escalate_at (0.80)?                          │── yes ──▶ ESCALATE  notify=True
       └───────────────────────┬──────────────────────────────┘
                              no
                                ▼
       ┌──────────────────────────────────────────────────────┐
  (3)  │ score <  clear_below (0.42)?                          │── yes ──▶ AUTO_CLEAR  notify=False
       └───────────────────────┬──────────────────────────────┘
                              no
                                ▼
       ┌──────────────────────────────────────────────────────┐
  (4)  │ borderline  [0.42, 0.80)                              │
       │   AI verdict "high"  ──────────────────────────────── │──▶ ESCALATE  notify=True  used_ai
       │   AI verdict "low"   ──────────────────────────────── │──▶ QUEUE     notify=False used_ai
       │   none / "medium"    ──────────────────────────────── │──▶ QUEUE     notify=False (human)
       └──────────────────────────────────────────────────────┘
```

`route()` accepts a `ScoredRecord` or its `.to_dict()` form, so the same call works in the
detector and behind the API. It returns
`Decision{action, notify, trail[], used_ai, reason}` — `trail[]` records which branch fired
(explainability), `reason` is the one-line human summary.

### Branch 4 — the borderline band and Gemini

Scores in `[0.42, 0.80)` are the genuinely ambiguous ones. Here the tree can take an optional
tie-breaking second opinion:

- **With a verdict** — `api/ingest.decide()` calls `gemini.classify(record)` →
  `{risk, confidence, rationale}` and passes it as `ai_verdict`. `risk=="high"` escalates +
  notifies; `risk=="low"` queues; `medium`/unknown falls through.
- **Without a verdict** — no `GEMINI_API_KEY`, SDK missing, or call failed → `classify` returns
  `None` and the branch **defaults to `QUEUE`** (human review). The safe default is a human, never
  an auto-clear or a silent escalation.

So Gemini only ever *refines* the borderline branch; it cannot move a critical-signal or
high-confidence escalation, nor rescue a clearly-benign score. See [GEMINI.md](GEMINI.md).

---

## Worked examples

**Ring burst (P4).** A May 17 QuickPay cross-card charge fires `merchant_burst_cross_card`.
Branch 1 matches on the critical signal — `ESCALATE`, `notify=True` — even if the per-row score is
mid-band. Trail: `critical signal fired: merchant_burst_cross_card`.

**Bust-out (P3).** `fraud_score=0.91`, reasons include `amount_vs_card_median`. Branch 1 already
matches the critical signal → `ESCALATE`, `notify=True`. (Branch 2 would catch it anyway since
`0.91 >= 0.80`.)

**Borderline (no critical signal).** `fraud_score=0.55`, only soft reasons. Branches 1–3 miss.
Branch 4: with no key, `ESCALATE` cannot happen → `QUEUE`, `notify=False`,
trail ends `no decisive AI verdict — defaulting to human review`. With Gemini returning
`risk="high"` → `ESCALATE`, `notify=True`, `used_ai=True`.

---

## Pure, tested, tunable

- **Pure** — `detector/decision_tree.py` has no web/db/network imports; it is import-safe and
  side-effect-free. DB write-through and alerts live in `api/`.
- **Unit-tested** — `tests/test_decision_tree.py` covers every branch; integration in
  `tests/test_ingest.py` confirms a bust-out escalates + notifies while a benign txn does not.
  Tests run with no secrets.
- **Tunable** — pass a custom `DecisionConfig` to move `clear_below` / `escalate_at` or change
  `critical_signals` without touching the scorer. Scores are produced upstream; the tree only
  routes them.
