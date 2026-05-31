"""Analyst notifications — the "should we email the fraud team?" output of the pipeline.

When the decision tree escalates a newly-ingested transaction (decision.notify == True),
`notify_analyst()` creates a notification addressed to FRAUD_ANALYST_EMAIL.

Per the chosen design, the shipped transport is **"log"**: the alert is recorded (in the
Mongo `notifications` collection + an in-memory list served by GET /notifications) but not
actually emailed. `_send()` is a single pluggable seam — swap in SMTP or a transactional
email API later without touching the pipeline.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from api import config, db

logger = logging.getLogger("fraudhunter.notifications")

# In-memory read cache (newest last); mirrors the Mongo `notifications` collection.
NOTIFICATIONS: list[dict] = []


def _send(notification: dict) -> bool:
    """Pluggable transport. Returns True if actually dispatched.

    "log"  -> record only (default; returns False = not sent).
    "smtp"/"api" -> extension points; not implemented, logged and treated as not-sent.
    """
    transport = config.NOTIFY_TRANSPORT
    if transport == "log":
        logger.info(
            "[ALERT] would notify %s: %s", notification["to"], notification["subject"]
        )
        return False
    logger.warning("NOTIFY_TRANSPORT='%s' not implemented — alert recorded only.", transport)
    return False


def notify_analyst(record: dict, decision) -> dict:
    """Create + persist an analyst alert for an escalated transaction."""
    score = record.get("fraud_score", 0.0)
    reasons = record.get("reasons", []) or []
    top = reasons[0]["text"] if reasons else "no specific signal"
    subject = (
        f"[Fraud Hunter] Escalation: {record.get('transaction_id')} "
        f"(${record.get('amount')}, score {score})"
    )
    body = (
        f"Transaction {record.get('transaction_id')} on {record.get('card_id')} was "
        f"auto-escalated by the decision tree.\n\n"
        f"Amount: ${record.get('amount')} at {record.get('merchant')} "
        f"({record.get('category')}, {record.get('merchant_country')}, {record.get('channel')})\n"
        f"Fraud score: {score}\n"
        f"Top signal: {top}\n"
        f"Routing: {' -> '.join(getattr(decision, 'trail', []) or [decision.action])}\n"
    )

    notification = {
        "notification_id": f"ntf_{uuid.uuid4().hex[:8]}",
        "transaction_id": record.get("transaction_id"),
        "to": config.FRAUD_ANALYST_EMAIL,
        "subject": subject,
        "body": body,
        "action": decision.action,
        "score": score,
        "transport": config.NOTIFY_TRANSPORT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sent": False,
    }
    notification["sent"] = _send(notification)

    col = db.notifications_col()
    if col is not None:
        try:
            col.insert_one(dict(notification))
        except Exception as exc:  # pragma: no cover - persistence is best-effort
            logger.warning("Failed to persist notification (%s).", exc)

    NOTIFICATIONS.append(notification)
    return notification


def list_notifications() -> list[dict]:
    """Newest first, with Mongo's _id stripped for JSON safety."""
    return [{k: v for k, v in n.items() if k != "_id"} for n in reversed(NOTIFICATIONS)]


def load_from_mongo() -> None:
    """Populate the in-memory cache from Mongo at startup."""
    NOTIFICATIONS.clear()
    col = db.notifications_col()
    if col is None:
        return
    try:
        for doc in col.find().sort("created_at", 1):
            doc.pop("_id", None)
            NOTIFICATIONS.append(doc)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load notifications from Mongo (%s).", exc)
