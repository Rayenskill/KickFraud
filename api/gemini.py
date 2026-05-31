"""Gemini integration — two jobs, both optional and gracefully degrading.

1. `summarize(record)` — a 1-2 sentence plain-language risk narrative + recommended action
   shown to the reviewer in the UI (lazy, cached per transaction_id).
2. `classify(record)` — a structured {risk, confidence, rationale} verdict used by the
   decision tree (detector/decision_tree.py) as a tie-breaker on borderline scores.

If `GEMINI_API_KEY` is unset, the `google-genai` package is missing, or any call fails,
every function returns None. Callers treat None as "no AI available": the decision tree
falls back to pure rules and the UI simply hides the AI panel. Detection never depends on
the network being up.
"""
from __future__ import annotations

import json
import logging

from api import config

logger = logging.getLogger("fraudhunter.gemini")

# In-memory summary cache (transaction_id -> text). The ingestion/startup path also
# persists summaries onto the Mongo document so they survive a restart.
_summary_cache: dict[str, str] = {}
_client = None
_client_init = False


def _get_client():
    global _client, _client_init
    if _client_init:
        return _client
    _client_init = True
    if not config.gemini_enabled():
        return None
    try:
        from google import genai

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini client initialized (model=%s).", config.GEMINI_MODEL)
    except Exception as exc:  # package missing or bad key
        logger.warning("Gemini unavailable (%s) — AI features disabled.", exc)
        _client = None
    return _client


def _reason_lines(record) -> str:
    reasons = record.get("reasons", []) if isinstance(record, dict) else getattr(record, "reasons", [])
    lines = []
    for r in reasons or []:
        text = r.get("text") if isinstance(r, dict) else getattr(r, "text", None)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if lines else "- (no signals fired)"


def _facts(record) -> str:
    g = (lambda k, d="": record.get(k, d)) if isinstance(record, dict) else (lambda k, d="": getattr(record, k, d))
    return (
        f"transaction_id: {g('transaction_id')}\n"
        f"amount: {g('amount')} (card median {g('card_median')})\n"
        f"merchant: {g('merchant')} [{g('category')}, {g('merchant_country')}, {g('channel')}]\n"
        f"fraud_score: {g('fraud_score')}\n"
        f"signals that fired:\n{_reason_lines(record)}"
    )


def _generate(prompt: str, *, json_mode: bool = False) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs = {"model": config.GEMINI_MODEL, "contents": prompt}
        try:
            from google.genai import types

            kwargs["config"] = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json" if json_mode else "text/plain",
            )
        except Exception:
            pass  # older SDK without typed config — send plain prompt
        resp = client.models.generate_content(**kwargs)
        return (getattr(resp, "text", None) or "").strip() or None
    except Exception as exc:
        logger.warning("Gemini call failed (%s).", exc)
        return None


def summarize(record) -> str | None:
    """Plain-language risk summary for the reviewer UI. Cached per transaction."""
    tid = record.get("transaction_id") if isinstance(record, dict) else getattr(record, "transaction_id", "")
    if tid and tid in _summary_cache:
        return _summary_cache[tid]

    prompt = (
        "You are a fraud-analysis assistant. In 1-2 plain sentences, explain why this card "
        "transaction is or isn't suspicious and recommend an action (clear, review, or "
        "escalate). Be concrete; reference the numbers. Do not invent facts beyond those "
        "given.\n\n" + _facts(record)
    )
    text = _generate(prompt)
    if text and tid:
        _summary_cache[tid] = text
    return text


def classify(record) -> dict | None:
    """Structured tie-breaker verdict for the decision tree's borderline branch.

    Returns {"risk": "high|medium|low", "confidence": 0..1, "rationale": str} or None.
    """
    prompt = (
        "You are a fraud-risk classifier. Given the transaction facts, respond with a JSON "
        'object: {"risk": "high"|"medium"|"low", "confidence": number 0..1, "rationale": '
        'short string}. Judge risk relative to the card\'s own behavior; a single foreign '
        "or geo-mismatched charge alone is usually low risk.\n\n" + _facts(record)
    )
    raw = _generate(prompt, json_mode=True)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        # Best-effort: pull the first {...} block if the model wrapped it in prose.
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except Exception:
            return None
    risk = str(data.get("risk", "medium")).lower()
    if risk not in ("high", "medium", "low"):
        risk = "medium"
    return {
        "risk": risk,
        "confidence": float(data.get("confidence", 0.0) or 0.0),
        "rationale": str(data.get("rationale", "")),
    }


def cache_summary(tid: str, text: str) -> None:
    """Pre-warm the cache from a persisted Mongo `ai_summary` field."""
    if tid and text:
        _summary_cache[tid] = text
