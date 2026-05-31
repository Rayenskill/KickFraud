"""Centralized environment configuration (loaded from .env if present).

All external-service wiring (MongoDB Atlas, Gemini, analyst notifications) is configured
here so the rest of the app reads typed settings instead of os.environ scattered around.
Everything has a safe default; missing secrets degrade gracefully (see api/db.py,
api/gemini.py) rather than crashing — the demo always runs.
"""
from __future__ import annotations

import os

# Load .env from the repo root if python-dotenv is installed. Optional: production
# environments may inject real env vars instead of a file.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:  # dotenv not installed or unreadable .env — fall back to os.environ
    pass


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# --- MongoDB (Atlas) -------------------------------------------------------
# Empty MONGO_URI => the app runs in CSV-backed in-memory mode (graceful fallback).
MONGO_URI: str = _get("MONGO_URI")
MONGO_DB: str = _get("MONGO_DB", "fraudhunter")
TRANSACTIONS_COLLECTION = "transactions"
AUDIT_COLLECTION = "audit"
NOTIFICATIONS_COLLECTION = "notifications"

# --- Gemini ----------------------------------------------------------------
# Empty GEMINI_API_KEY => summaries/classification return None and the decision tree
# falls back to pure rules.
GEMINI_API_KEY: str = _get("GEMINI_API_KEY")
GEMINI_MODEL: str = _get("GEMINI_MODEL", "gemini-2.0-flash")

# --- Notifications ---------------------------------------------------------
# Who gets alerted when the decision tree escalates a new transaction.
FRAUD_ANALYST_EMAIL: str = _get("FRAUD_ANALYST_EMAIL", "fraud-analyst@example.com")
# Transport for analyst alerts: "log" (record only) is the shipped default; "smtp"/"api"
# are left as pluggable extension points (see api/notifications.py).
NOTIFY_TRANSPORT: str = _get("NOTIFY_TRANSPORT", "log")


def gemini_enabled() -> bool:
    return bool(GEMINI_API_KEY)


def mongo_configured() -> bool:
    return bool(MONGO_URI)
