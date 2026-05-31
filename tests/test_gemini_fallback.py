"""Gemini must degrade gracefully: with no API key, summarize/classify return None and
detection/routing fall back to pure rules. These tests never touch the network.
"""
from api import config, gemini


def _disable(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    # Force the lazy client to re-evaluate against the (now empty) key.
    gemini._client = None
    gemini._client_init = False


def test_classify_returns_none_without_key(monkeypatch):
    _disable(monkeypatch)
    assert gemini.classify({"transaction_id": "t1", "reasons": []}) is None


def test_summarize_returns_none_without_key(monkeypatch):
    _disable(monkeypatch)
    assert gemini.summarize({"transaction_id": "t2", "reasons": []}) is None


def test_config_reports_disabled(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    assert config.gemini_enabled() is False
