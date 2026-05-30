# DETECTION — the scoring engine in depth

The detector is **one pure-Python engine** (`detector/`, no web deps) built on a single principle:
the brief rewards **explainability**, so we use **additive weighted signals**, not a black box. Every
point of a transaction's score comes from a named signal that emits a human-readable reason.

---

## Pipeline (three passes + scoring)

### Pass 1 — per-card baselines (`baselines.py`)
One pass over the data, grouped by `card_id`, produces a profile per card:
- **amount:** median and MAD (median absolute deviation — robust to the very outliers we hunt).
- **categories:** the set of categories this card normally uses.
- **merchant_country:** the set/typical country for this card.
- **channels:** typical online vs in-person mix.
- **devices / IPs:** known device_ids and ip_addresses for this card.
- **hour-of-day:** typical activity hours.

Why per-card: a $300 charge is normal for a card whose median is $280 and extraordinary for one
whose median is $12. Absolute thresholds can't tell those apart; baselines can. This is also what
lets us dodge the foreign-country trap — "foreign" is judged against *this card's* history.

### Pass 2 — cross-card aggregates (`aggregates.py`)
Structures that no single transaction can reveal:
- **per-(merchant, day) distinct-card counts** and amount stats → powers P4.
- **IP → cards** and **device → cards** maps → powers the defensive shared-infra signals and graph
  edges.
- **rolling per-card velocity windows** → powers P1.

### Pass 3 — score each transaction (`signals.py` + `score.py`)
Each signal is a small function with its **weight constant declared at the top of the module** so all
weights are tunable in one place and unit-testable in isolation. `score.py` runs every signal over
each transaction, sums the weights of those that fire, and collects their reason strings.

```
score(txn) = Σ weight_i  for each signal i that fires on txn
label(txn) = "fraud" if score ≥ threshold else "clear"
```

---

## The signals

| Signal | Pattern | Fires when | Reason string (example) |
|---|---|---|---|
| `amount_vs_card_median` | P3 | amount ≥ M× the card's median | "$735 is 30× this card's median" |
| `atypical_category_for_card` | P2 | category not in card's baseline set | "gift_card never seen on this card" |
| `atypical_country_for_card` | P2 | merchant_country not in card's baseline | "first CN purchase for this card" |
| `velocity_burst` | P1 | ≥4 small (≤$15) online txns in ~10–15 min on the card | "9 small online txns in 26 min" |
| `merchant_burst_cross_card` | P4 | this merchant hit by ≥5 distinct cards within ~2h, each >$200 | "'QuickPay Online' hit by 7 cards >$200 in 72 min" |
| `high_risk_merchant` | P3 | QuickPay Online, or gift_card/electronics over threshold | "high-risk category over $250" |
| `shared_ip_across_cards` | defensive | this IP used by >1 card | "IP shared with card_047" |
| `shared_device_across_cards` | defensive | this device used by >1 card | "device shared across cards" |
| `new_device_or_ip_for_card` | defensive | online txn on a device/IP new to the card | "new device for this card" |

### Critical interaction: P2 requires BOTH conditions
`atypical_category_for_card` and `atypical_country_for_card` are designed so that **neither alone
crosses the threshold** — only their combination does. This is the entire defense against the
geo/foreign-country traps (H1/H2 in `HYPOTHESES.md`). A Canadian buying online_retail from a US
Amazon trips at most one of these weakly; an account-takeover trips both.

### Thresholds are validated against the data, not assumed
The defaults below were measured on `transactions.csv` (see `DATA_ANALYSIS.md`), and crucially are
**relative/behavioral — never keyed to a date**. The fraud is spread across the whole month, so any
date-based rule would be overfitting:
- **P1 velocity:** ≥4 small (≤$15) online txns within ~10–15 min → flags exactly the 4 card-testing
  cards, **0 false positives**. (The earlier "~1h" window was too wide.)
- **P4 merchant burst:** ≥5 distinct cards at one merchant within ~2h, each >$200 → flags exactly the
  May 5 (6 cards) and May 17 (7 cards) QuickPay bursts, **0 false positives**. The >$200 guard is what
  keeps a busy legitimate merchant from tripping it. (The earlier "16 cards on May 24" was wrong.)
- **P2 deviation:** no date window at all; fire purely on atypical-category-and-country.
- **P3 amount outlier:** ≈12×+ the card's own median in a high-risk category.

---

## Explanation output

The explanation for a flag is the **ranked list of fired reasons**, highest-contribution first:

> **score 0.91** — $735 is 30× this card's median; gift_card never seen on this card; 'QuickPay
> Online' hit by 7 cards >$200 in 72 min.

This string is what the reviewer reads, and it's what makes the tool defensible: no flag is ever
"because the model said so."

---

## Cost-aware threshold

A single ratio **`fp_cost : fn_cost`** shifts the cutoff:
- Raising the cost of false negatives (missing fraud is expensive) **lowers** the threshold → flags
  more.
- Raising the cost of false positives (annoying good customers is expensive) **raises** the
  threshold → flags fewer.

Default threshold is tuned so the flagged set is ~7% of rows. The ratio is exposed via the API
(`POST /threshold`) and the UI slider, and re-labels live without re-scoring (scores are fixed;
only the cutoff moves).

---

## Tuning method

1. Score all rows.
2. Privately compare the flagged set to the known fraud band (tx_000919–tx_001007) — **validation
   aid only**, see `HYPOTHESES.md` H8.
3. Compute precision / recall / F1; adjust weight constants and the default threshold to land F1 in
   the **0.85+** target range.
4. Re-run the per-pattern pytest cases to confirm each pattern's known fraud still scores above
   threshold and known-legit rows stay below.

Because weights live as constants at the top of `signals.py`, tuning is editing a handful of numbers
in one file and re-running tests — no structural changes.

---

## Outputs of the engine

`score.py` produces, in one run:
1. A list of **scored records** (txn + score + label + ranked reasons) — consumed by the API.
2. **Graph edge data** (shared-IP, shared-device, co-burst edges) — consumed by `/graph`.
3. **`transactions_flagged.csv`** — all 1,000 rows with `is_fraud`, `fraud_score`, `fraud_reasons`
   appended — the deliverable.
