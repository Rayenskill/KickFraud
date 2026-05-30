"""Per-pattern detection tests: one known fraud + one known legit per pattern.

Target: F1 >= 0.85 on the PRIVATE injected-fraud band (high transaction_id,
tx_000919..tx_001007, ~77 rows). The band is a check ONLY, never a signal
(docs/CORRECTIONS.md, docs/TESTING.md). There is no is_fraud column in the CSV.

Scaffolded as skips until detector.score() lands (step 1).
"""
import pytest

pytestmark = pytest.mark.skip(reason="detector not implemented yet — step 1")


def test_p1_card_testing_burst_flags_fraud():
    # >=4 small (<=$15) online txns in ~10-15 min on a card scores above threshold.
    ...


def test_p1_legit_slow_small_spend_stays_clear():
    # Normal small purchases spread out stay below threshold.
    ...


def test_p4_quickpay_cross_card_burst_flags_fraud():
    # >=5 cards >$200 at QuickPay Online within ~2h are flagged (May 5 + May 17 bursts).
    ...


def test_p4_busy_legit_merchant_stays_clear():
    # A busy merchant with many <$200 charges does NOT trip the burst rule (the >$200 guard).
    ...


def test_p2_atypical_category_and_country_flags_fraud():
    # atypical category AND country together cross threshold (neither alone does).
    ...


def test_p2_oneoff_legit_foreign_purchase_stays_clear():
    # A single Spotify(SE)/AliExpress(CN) buy is NOT flagged.
    ...


def test_p3_bustout_amount_outlier_flags_fraud():
    # amount >= ~12x card median + high-risk category is flagged.
    ...


def test_p3_normal_large_but_typical_purchase_stays_clear():
    # A large-but-typical purchase for that card stays clear.
    ...
