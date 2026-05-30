# Data Analysis — what's actually in `transactions.csv`

> This is the evidence base. Detection is grounded in these observations. **Every figure below was
> re-derived directly from the 1,000-row file** (not assumed), after an earlier draft of this plan
> got several dates wrong. Where the earlier draft was wrong, it's flagged.

## Dataset shape

- **1,000 rows**, **50 cards** (`card_000`–`card_049`), spanning late April → late May 2026.
- Columns: `transaction_id`, `timestamp`, `card_id`, `amount`, `merchant_name`,
  `merchant_category`, `channel` (online / in_person / atm), `cardholder_country`,
  `merchant_country`, `device_id`, `ip_address`.
- Amount: median ~$28, max **$1,900**. Most legitimate spend is small and routine.

## ⚠️ Correction to the original framing

The original plan claimed fraud was **"concentrated in coordinated waves in the final week
(2026-05-18 → 05-24)."** **This is false.** Re-analysis shows the fraud is **spread across the entire
month (late April → late May)**. The *mechanisms* are real and coordinated, but they are **not
confined to the final week**, and several specific dates in the first draft were wrong. The detection
signals must therefore be **relative / behavioral, never keyed to a date window** — which is what the
signal design always intended, but the descriptive dates were misleading and are corrected below.

## The four patterns (re-verified)

### P1 — Card-testing micro-bursts
A single card fires a tight burst of **~8–12 tiny (≤$15) online transactions**, alternating CA/CN
merchants. **The burst is fast: ~22–26 minutes, with sub-2-minute micro-clusters** — *not* the ~1
hour the first draft claimed. Cards and their bursts:

| Card | Date | Burst window | Small online txns |
|---|---|---|---|
| card_042 | May 3 | ~10:58–11:20 (~22 min) | 8 |
| card_038 | May 11 | ~13:46–14:08 (~23 min) | 10 |
| card_023 | May 12 | ~05:12–05:38 (~26 min) | 11 |
| card_049 | May 14 | ~21:46–22:11 (~26 min) | 12 |

Example of the speed: **card_049 fired 4 txns in 1m48s** (21:46:00 → 21:47:48). The first draft's
"~1h" window was too wide.
- **Detectable by:** per-card velocity — **≥4 small (≤$15) online txns within ~10–15 min**.
- **Validated:** this rule flags exactly cards 042/023/038/049 and **zero** other cards.

### P2 — Account-takeover foreign spree
Cards buying from **AliExpress (CN)** when they otherwise never transact with CN merchants. The first
draft (and the review feedback) treated this as **"40 AliExpress txns across 24 cards, clustered May
18–22."** Two corrections:
1. **Not clustered May 18–22.** These txns span **April 27 → May 23** (only ~8 of 40 fall in that
   window). The date cluster was wrong.
2. **40 is an over-count.** Cross-checked against the injected-fraud band (see validation section),
   only ~10 of the 40 AliExpress txns are genuinely injected fraud — and they sit on the **same cards
   as the P1 card-testing bursts** (042, 023, 038, 049, 048). The other ~30 AliExpress orders are
   spread one-or-two-per-card across 19 cards and look like **legitimate** budget online shopping.
   **Raw AliExpress volume is itself a mild trap.**
- **Detectable by:** **per-card behavioral deviation, no date window** — category (online_retail)
  atypical for the card **and** merchant_country (CN) atypical for the card. **Precision caveat:** a
  single atypical foreign order is *not* enough — a normal person's one-off AliExpress buy trips it.
  Strengthen the signal: require **multiple** atypical foreign orders, or combine with velocity/amount,
  so it fires on genuine takeovers and not on one legitimate foreign purchase.

### P3 — Gift-card / electronics bust-out
**High-value buys ($378–$1,900) in `gift_card`/`electronics` at 12×–55× the card's own median.** Cards
**016, 018, 020, 021, 045** (and 000, 030, 019). **Spread May 6 → May 21 — NOT "May 23–24"** as the
first draft said (same date error as the others). Amounts and multiples match the original claim; only
the date was wrong.
- **Detectable by:** per-card amount outlier (multiple of median) + high-risk category. Date-independent.

### P4 — Coordinated processor attack (cross-card)
**Two** coordinated high-value bursts at **"QuickPay Online"**, each many distinct cards in ~72
minutes — **not** the single "16 cards on May 24" the first draft claimed. **May 24 has exactly one
$92.60 QuickPay charge.** The real bursts:

| Burst | Window (~72 min) | Cards each >$200 | Amount range |
|---|---|---|---|
| **May 5** | 02:15:14 → 03:27:16 | **6** (032, 037, 002, 038, 039, 046) | $356–$935 |
| **May 17** | 14:10:26 → 15:22:21 | **7** (037, 009, 030, 036, 029, 040, 007) | $311–$835 |

(card_037 appears in both.) No single card looks unusual alone — the signal only exists across cards.
- **Detectable by:** cross-card merchant burst — **≥5 distinct cards at one merchant within ~2h, each
  >$200**.
- **Validated:** this rule flags exactly the May 5 and May 17 QuickPay bursts and **nothing else** —
  no other merchant, and not the lone May 24 charge.

## The traps (look like fraud, aren't)

- **Geo-mismatch (cardholder_country ≠ merchant_country) is mostly legit** — normal for cross-border
  online retail (e.g. a Canadian on Amazon.com US). Mismatch alone is **not** a fraud signal.
- **Foreign `merchant_country` alone is legit.** Spotify is SE, Netflix billing varies, AliExpress is
  CN. A foreign country by itself means nothing; it only matters *relative to that card's baseline*
  and *combined* with an atypical category (that's exactly the P2 design).
- **Device/IP sharing is near-zero.** Raw device reuse across cards ≈ 0; IP reuse is a single pair.
  So the cross-card signal is **merchant-burst**, not shared infrastructure. The graph's meaningful
  edges are co-burst edges, not device/IP edges.

## Validation aid (private — NEVER ship as a signal)

The injected fraud forms a **clean band at the top of the `transaction_id` range: id ≥ ~931, which is
77 rows ≈ 7.7%** — matching the stated ~7% fraud. It is **91% online** and dominated by exactly the
suspicious merchants (QuickPay, Shopify Merchants, AliExpress, gift-card/electronics). The two
QuickPay bursts are literally the highest IDs in the file (May 5 = ids 995–1000, May 17 = ids
1001–1007). The band spans **May 3 → May 24**.

This band is a reliable **private ground-truth label** for estimating precision/recall in the test
harness — and it's how we caught the P2 over-count above. It is **never** a detection feature: it
wouldn't generalize, and shipping it would be cheating. Keep it in the validation harness only, never
in `signals.py`.

## Threshold validation summary (measured on this file)

| Pattern | Rule | Result on the data |
|---|---|---|
| P1 | ≥4 small (≤$15) online txns in ~15 min | flags exactly 4 cards, 0 false positives |
| P4 | ≥5 distinct cards / merchant / ~2h, each >$200 | flags exactly the May 5 + May 17 bursts, 0 false positives |
| P2 | atypical category **and** country, ×N orders (no date) | ~10 genuine ATO txns on the burst cards; raw AliExpress count (40) over-states it |
| P3 | amount ≥ ~12× card median + high-risk category | recovers the listed bust-out cards (in-band) |

## Cleanup note

Delete any scratch analysis files (`Downloads\_an*.txt`, `/tmp/*.py`) before submission.
