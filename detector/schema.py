"""Frozen scored-record contract (Python side).

Mirrors `contract/scored_record.schema.json`, `docs/JSON_CONTRACT.md` and `web/src/types.ts`.
The contract is FROZEN (H0-H2). Changes require a sync with the UI owner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Enum values kept in sync with the JSON Schema.
LABELS = ("fraud", "clear")
CHANNELS = ("online", "in_person")
REVIEW_STATUSES = ("pending", "approved", "dismissed", "escalated")
DECISIONS = ("approve", "dismiss", "escalate")
NODE_TYPES = ("card", "merchant")
EDGE_TYPES = ("co_burst", "shared_ip", "shared_device")


@dataclass
class Reason:
    """One fired signal's contribution. `reasons` is ranked, weight-desc."""

    signal: str
    weight: float
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoredRecord:
    """The core object served by every read endpoint. See JSON_CONTRACT.md."""

    transaction_id: str          # e.g. "tx_001003"
    card_id: str
    timestamp: str               # ISO 8601, no TZ in source ("2026-05-17T14:11:07")
    amount: float
    merchant: str                # from CSV merchant_name
    merchant_country: str        # ISO-2
    category: str                # from CSV merchant_category
    channel: str                 # "online" | "in_person"
    card_median: float
    device_id: str | None = None
    ip_address: str | None = None
    fraud_score: float = 0.0     # 0..1, fixed at scoring time
    label: str = "clear"         # derived from current threshold
    reasons: list[Reason] = field(default_factory=list)
    review_status: str = "pending"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = [r if isinstance(r, dict) else r.to_dict() for r in self.reasons]
        return d


@dataclass
class GraphNode:
    id: str
    type: str                    # "card" | "merchant"
    flag_count: int | None = None
    suspicious: bool | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str                    # "co_burst" | "shared_ip" | "shared_device"
    weight: float | None = None
    ip: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
