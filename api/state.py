"""In-session review state: review-status map, suppression set, session weight overrides,
undo stack, audit log. No database — everything is session-scoped (docs/ARCHITECTURE.md, API.md).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

class ReviewState:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}          # transaction_id -> review_status
        self.suppressed: set[str] = set()         # hidden by the feedback loop
        self.weight_overrides: dict[str, float] = {}  # per-signal session multipliers
        self.undo_stack: list[dict] = []          # reversible actions
        self.audit_log: list[dict] = []           # append-only

    def record(self, txn: dict, all_records: list[dict], decision: str, reviewer: str) -> dict:
        """Apply approve/dismiss/escalate; on dismiss, run the feedback loop."""
        tid = txn["transaction_id"]
        old_status = self.status.get(tid, "pending")
        
        self.status[tid] = decision
        
        suppressed_this_time: set[str] = set()
        weight_nudged: str | None = None
        old_weight: float | None = None
        reason_at_decision = ""
        if txn.get("reasons"):
            reason_at_decision = txn["reasons"][0]["text"]

        if decision == "dismiss":
            # Feedback loop
            if txn.get("reasons"):
                top_reason = txn["reasons"][0]
                signal = top_reason["signal"]
                
                # Suppression logic
                if signal == "merchant_burst_cross_card":
                    # Suppress other pending flags for the same merchant
                    for r in all_records:
                        if (r["merchant"] == txn["merchant"] and 
                            self.status.get(r["transaction_id"], "pending") == "pending" and
                            r["transaction_id"] != tid and
                            r.get("reasons") and r["reasons"][0]["signal"] == signal):
                            suppressed_this_time.add(r["transaction_id"])
                else:
                    # Suppress other pending flags for the same card + same reason
                    for r in all_records:
                        if (r["card_id"] == txn["card_id"] and 
                            self.status.get(r["transaction_id"], "pending") == "pending" and
                            r["transaction_id"] != tid and
                            r.get("reasons") and r["reasons"][0]["signal"] == signal):
                            suppressed_this_time.add(r["transaction_id"])
                            
                self.suppressed.update(suppressed_this_time)
                
                # Nudge weight down
                old_weight = self.weight_overrides.get(signal, 1.0)
                self.weight_overrides[signal] = old_weight * 0.9
                weight_nudged = signal

        audit_id = f"aud_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        audit_entry = {
            "audit_id": audit_id,
            "transaction_id": tid,
            "reviewer": reviewer,
            "decision": decision,
            "reason_at_decision": reason_at_decision,
            "timestamp": now,
        }
        self.audit_log.append(audit_entry)

        # Push to undo stack
        self.undo_stack.append({
            "transaction_id": tid,
            "old_status": old_status,
            "suppressed": list(suppressed_this_time),
            "weight_nudged": weight_nudged,
            "old_weight": old_weight,
            "audit_id": audit_id
        })

        return {
            "transaction_id": tid,
            "review_status": decision,
            "suppressed": list(suppressed_this_time),
            "audit_id": audit_id
        }

    def undo(self) -> dict | None:
        """Reverse the last action fully (status, suppression, weight, audit)."""
        if not self.undo_stack:
            return None
            
        action = self.undo_stack.pop()
        tid = action["transaction_id"]
        
        # Restore status
        if action["old_status"] == "pending":
            if tid in self.status:
                del self.status[tid]
        else:
            self.status[tid] = action["old_status"]
            
        # Un-suppress
        for sid in action["suppressed"]:
            if sid in self.suppressed:
                self.suppressed.remove(sid)
                
        # Restore weight
        if action["weight_nudged"]:
            if action["old_weight"] == 1.0 and action["weight_nudged"] in self.weight_overrides:
                del self.weight_overrides[action["weight_nudged"]]
            else:
                self.weight_overrides[action["weight_nudged"]] = action["old_weight"]
                
        # Remove audit log entry
        self.audit_log = [e for e in self.audit_log if e["audit_id"] != action["audit_id"]]
        
        return {
            "undone": tid,
            "restored_status": action["old_status"]
        }
