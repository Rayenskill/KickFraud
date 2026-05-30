"""In-session review state: review-status map, suppression set, session weight overrides,
undo stack, audit log. No database — everything is session-scoped (docs/ARCHITECTURE.md, API.md).
"""
from __future__ import annotations


class ReviewState:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}          # transaction_id -> review_status
        self.suppressed: set[str] = set()         # hidden by the feedback loop
        self.weight_overrides: dict[str, float] = {}  # per-signal session multipliers
        self.undo_stack: list[dict] = []          # reversible actions
        self.audit_log: list[dict] = []           # append-only

    def record(self, transaction_id: str, decision: str, reviewer: str) -> dict:
        """Apply approve/dismiss/escalate; on dismiss, run the feedback loop. TODO (step 2)."""
        raise NotImplementedError("ReviewState.record — step 2")

    def undo(self) -> dict | None:
        """Reverse the last action fully (status, suppression, weight, audit). TODO (step 2)."""
        raise NotImplementedError("ReviewState.undo — step 2")
