# CORRECTIONS — plan claim vs. verified data

> After a teammate flagged the dates, **every pattern was re-checked directly against
> `transactions.csv`.** The plan's *mechanisms* were right; its *dates and several counts were wrong*.
> Ground truth is the injected-fraud band (high `transaction_id`, id ≥ ~931, 77 rows ≈ 7.7%, spanning
> **May 3 → May 24**). This page is the authoritative delta; full detail in `DATA_ANALYSIS.md` and
> `HYPOTHESES.md`.

## The headline error
**Plan said:** fraud is "concentrated in the final week (May 18–24)."
**Reality:** fraud is **spread across the whole month (May 3 → May 24)**. This false framing is what
produced the wrong per-pattern dates. **Fix:** all signals are relative / behavioral, never date-keyed.

## Per-pattern deltas

| # | Plan claimed | Verified reality | Verdict |
|---|---|---|---|
| **P4** QuickPay | 16 cards >$200 on **May 24** | **Two** bursts: **May 5** (6 cards >$200, 02:15–03:27) + **May 17** (7 cards >$200, 14:10–15:22). May 24 = one $92.60 charge. Burst txns are ids 995–1007 (top of the file). | ❌ plan wrong / ✅ friend right |
| **P1** card-testing | 8–11 tiny txns within **~1h** | 8–12 tiny online txns within **~22–26 min**, with sub-2-min micro-clusters (card_049: **4 txns in 1m48s**). | ❌ window too wide / ✅ friend right |
| **P2** AliExpress | 40 txns / 24 cards **clustered May 18–22** | Spread **Apr 27 → May 23**; and **40 over-counts** — only ~10 are injected fraud (on the P1 burst cards); ~30 look legitimate. | ⚠️ both plan and friend over-counted; friend right on "spread" |
| **P3** bust-out | $250–$1,900, 10–55× median, **May 23–24** | $378–$1,900, 12–55× median, **spread May 6 → May 21**. Amounts/multiples correct; date wrong. | ❌ date wrong (friend didn't flag it) |

## Validated detection rules (measured, 0 false positives unless noted)

| Pattern | Rule (relative/behavioral) | Result on this file |
|---|---|---|
| P1 | ≥4 small (≤$15) online txns in ~10–15 min | flags exactly cards 042/023/038/049 — 0 FP |
| P4 | ≥5 distinct cards / merchant / ~2h, each >$200 | flags exactly May 5 + May 17 QuickPay — 0 FP |
| P2 | atypical category **and** country, **require ×N orders** (no date) | needs the ×N guard, else it flags one-off legit foreign buys |
| P3 | amount ≥ ~12× the card's median + high-risk category | recovers the in-band bust-out cards |

## What this means for the build
1. **Delete every fixed date from the detection logic.** Sliding windows + per-card baselines only.
2. **P4:** keep the **>$200 guard** — it's what stops a busy legit merchant from tripping the burst rule.
3. **P1:** tighten the velocity window to ~10–15 min.
4. **P2:** don't equate AliExpress volume with fraud; require **multiple** atypical foreign orders (or
   combine with velocity/amount), or precision drops on legitimate one-off foreign purchases.
5. **Validation:** use the id ≥ ~931 band as a **private** recall/precision check only — never as a
   shipped signal.
