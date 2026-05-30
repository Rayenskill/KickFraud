# HYPOTHESES — fraud detection hypothesis log

> A running record of what we suspected, how we tested it against the data, and the verdict. **All
> figures here were re-derived directly from `transactions.csv`.** An earlier draft hard-coded
> several wrong dates ("final week," "May 24," "May 18–22," "May 23–24"); those are corrected and the
> correction itself is logged as H9.

Legend: ✅ confirmed (became a signal) · ⚠️ partial (refined) · ❌ rejected (trap / dropped).

---

## H1 — "Foreign merchant country means fraud" ❌ REJECTED → trap
Foreign `merchant_country` ≠ fraud. Spotify=SE, AliExpress=CN are legitimately foreign. Predictive
only *relative to a card's own baseline* and *combined* with another deviation. Recorded as a trap.

## H2 — "Geo-mismatch (cardholder ≠ merchant country) means fraud" ❌ REJECTED → trap
Mismatch is the normal state for cross-border online retail (Canadian → Amazon.com US). Not
predictive. Second trap. Reinforces "combined deviation, not absolute rule."

## H3 — "Account takeover: a card suddenly buys a foreign online category it never used" ⚠️ PARTIAL → P2 (refined)
**Test:** per-card category + country baselines, cross-checked against the injected-fraud band.
**Finding:** the "**40 AliExpress / 24 cards**" framing is **over-counted**. Only ~10 of those 40 are
genuinely injected fraud, and they sit on the **same cards as the P1 bursts** (042, 023, 038, 049,
048). The other ~30 AliExpress orders (one or two per card across 19 cards) look **legitimate**.
⚠️ **Correction:** spread **April 27 → May 23**, *not* "clustered May 18–22."
**Verdict:** Real but subtle. Signal = **date-independent behavioral deviation** (atypical category
**and** country). **Precision caveat:** one atypical foreign order isn't enough (a normal one-off
AliExpress buy trips it) — require **multiple** atypical foreign orders or combine with
velocity/amount. Raw AliExpress volume is itself a mild trap.

## H4 — "Card testing: rapid tiny online charges" ✅ CONFIRMED → P1
**Test:** per-card rolling windows over small (≤$15) online txns.
**Finding:** cards 042 (May 3), 038 (May 11), 023 (May 12), 049 (May 14) each fired **~8–12 tiny
online txns**, alternating CA/CN. ⚠️ **Correction:** the bursts are **~22–26 min, with sub-2-min
micro-clusters** (card_049 did **4 txns in 1m48s**) — *not* the "~1h" the first draft claimed.
**Verdict:** Confirmed. Signal `velocity_burst` tightened to **≥4 small online txns in ~10–15 min**.
**Validated:** flags exactly those 4 cards, 0 false positives.

## H5 — "Bust-out: a couple of huge buys far above the card's normal" ✅ CONFIRMED → P3
**Finding:** buys of **$378–$1,900 at 12×–55× the card median** in `gift_card`/`electronics` on cards
016, 018, 020, 021, 045 (and 000, 030, 019). ⚠️ **Correction:** spread **May 6 → May 21**, *not* "May
23–24." Amounts/multiples match the first draft; only the date was wrong.
**Verdict:** Confirmed. Signal `amount_vs_card_median` + high-risk category. Date-independent.

## H6 — "Coordinated attack: one merchant hit by many cards at once" ✅ CONFIRMED → P4
**Test:** per-(merchant, sliding-window) distinct-card counts on high-value charges.
**Finding:** **two** QuickPay Online bursts — **May 5 (6 cards >$200, 02:15–03:27)** and **May 17 (7
cards >$200, 14:10–15:22)**, each ~72 min. ⚠️ **Major correction:** the first draft's "**16 cards on
May 24**" is wrong on every count — **May 24 has a single $92.60 charge**, and the real attack is two
~6–7-card bursts on May 5 and May 17.
**Verdict:** Confirmed. Signal `merchant_burst_cross_card` = **≥5 distinct cards / merchant / ~2h,
each >$200**, sliding window, **no fixed date**. **Validated:** flags exactly those two bursts, 0
false positives. This is the pattern the ring graph visualizes.

## H7 — "Fraudsters share devices/IPs across cards" ⚠️ PARTIAL → defensive only
Raw device reuse across cards ≈ 0; IP reuse is a single pair. Keep `shared_ip_across_cards` /
`shared_device_across_cards` as cheap defensive signals (they generalize, cost nothing) but they are
**not** the cross-card workhorse — merchant-burst is.

## H8 — "High transaction_id means fraud" ✅ CONFIRMED (band) → validation aid only, never shipped
**Test:** characterized the high-id rows.
**Finding:** injected fraud is a **clean band, id ≥ ~931 (77 rows ≈ 7.7%)**, 91% online, dominated by
the suspicious merchants; the QuickPay bursts are the very highest ids (995–1007). It's a **reliable
private ground-truth label** — and is how the P2 over-count (H3) was caught.
**Verdict:** Useful **for validation only**. **Never a shipped signal** — it wouldn't generalize and
would be cheating. Stays in the test harness, never in `signals.py`.

## H9 — "Fraud is concentrated in the final week (May 18–24)" ❌ REJECTED → corrected framing
**The original plan's central framing.** **Test:** dated every fraud cluster.
**Finding:** P1 spans May 3–14; P2 spans Apr 27–May 23; P3 spans May 6–21; P4 is May 5 + May 17. **None
is confined to May 18–24.** The fraud is spread across the **whole month**.
**Verdict:** Rejected. The "final week" framing is false and was the root cause of the wrong dates in
H3/H4/H5/H6. **Lesson:** signals must be relative/behavioral; descriptive dates from one sample must
never become thresholds (classic overfitting).

---

## Summary: hypotheses → signals

| Hypothesis | Verdict | Outcome |
|---|---|---|
| H1 foreign country | ❌ | trap |
| H2 geo-mismatch | ❌ | trap |
| H3 atypical category+country | ⚠️ | P2 signal — refined; 40 AliExpress over-counts, ~10 genuine; needs ×N guard |
| H4 velocity burst | ✅ | P1 signal (≥4 in ~15 min; bursts ~25 min) |
| H5 amount outlier + category | ✅ | P3 signal (spread May 6–21) |
| H6 cross-card merchant burst | ✅ | P4 signal (May 5 + May 17, ≥5 cards/2h/>$200) |
| H7 shared device/IP | ⚠️ | defensive low-weight signal |
| H8 transaction_id band | ✅ | clean band id≥931 (~7.7%); private validation aid only, never shipped |
| H9 "final week" framing | ❌ | corrected — fraud spans the whole month |
