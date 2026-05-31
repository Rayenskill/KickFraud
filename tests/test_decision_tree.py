"""Unit tests for the business-logic decision tree (detector/decision_tree.py).

Covers every branch: critical signal, high score, auto-clear, and the borderline branch
with/without an AI tie-breaker verdict.
"""
from detector.decision_tree import (
    AUTO_CLEAR,
    ESCALATE,
    QUEUE,
    route,
)


def _rec(score, signals=()):
    return {
        "fraud_score": score,
        "reasons": [{"signal": s, "weight": 0.1, "text": s} for s in signals],
    }


def test_critical_signal_escalates_and_notifies():
    d = route(_rec(0.50, ["merchant_burst_cross_card"]))
    assert d.action == ESCALATE
    assert d.notify is True


def test_amount_outlier_is_critical():
    d = route(_rec(0.55, ["amount_vs_card_median"]))
    assert d.action == ESCALATE
    assert d.notify is True


def test_high_score_escalates():
    d = route(_rec(0.92))
    assert d.action == ESCALATE
    assert d.notify is True


def test_low_score_auto_clears():
    d = route(_rec(0.10))
    assert d.action == AUTO_CLEAR
    assert d.notify is False


def test_borderline_without_ai_goes_to_queue():
    d = route(_rec(0.50, ["new_device_or_ip_for_card"]))
    assert d.action == QUEUE
    assert d.notify is False
    assert d.used_ai is False


def test_borderline_ai_high_escalates():
    d = route(_rec(0.50, ["new_device_or_ip_for_card"]), ai_verdict={"risk": "high", "confidence": 0.9})
    assert d.action == ESCALATE
    assert d.notify is True
    assert d.used_ai is True


def test_borderline_ai_low_queues():
    d = route(_rec(0.50, ["new_device_or_ip_for_card"]), ai_verdict={"risk": "low", "confidence": 0.8})
    assert d.action == QUEUE
    assert d.notify is False
    assert d.used_ai is True


def test_trail_is_populated():
    d = route(_rec(0.92))
    assert d.trail and isinstance(d.trail, list)
