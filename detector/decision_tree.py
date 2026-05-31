"""Business-logic decision tree — routes a scored transaction to an action.

This is the layer between *detection* (a 0..1 score + reasons) and *operations* (what do
we actually DO with this transaction?). It is intentionally **pure**: no web, no DB, no
network. That keeps it unit-testable and means the same tree runs in batch scoring, in the
live-ingestion pipeline, and in the docs (the branches below are the diagram in
docs/DECISION_TREE.md).

Routing outcomes
----------------
    AUTO_CLEAR  score below the clear threshold — no human time spent.
    QUEUE       send to the human review queue (the normal path for a flag).
    ESCALATE    high-confidence / coordinated fraud — notify the on-call analyst.

The `notify` flag on an ESCALATE is what triggers the analyst email/alert in
`api/notifications.py`. Borderline scores (between the two thresholds) can optionally
consult Gemini for a tie-breaking second opinion; with no AI verdict they default to the
safe choice of human review.

`route()` accepts either a `ScoredRecord` or its `.to_dict()` form so the same call works
in the detector and behind the API.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# --- routing outcomes ------------------------------------------------------
AUTO_CLEAR = "auto_clear"
QUEUE = "queue"
ESCALATE = "escalate"
ACTIONS = (AUTO_CLEAR, QUEUE, ESCALATE)


@dataclass
class DecisionConfig:
    """Tunable thresholds + the signals that force an escalation on their own.

    Mirrors the cost-aware threshold model in detector/score.py: `clear_below` is the
    default fraud cutoff (0.42). Anything at/above `escalate_at` is treated as
    high-confidence fraud. The critical signals escalate regardless of score because a
    coordinated cross-card ring (P4) or an extreme amount outlier (P3) is operationally
    urgent even if the normalized score sits in the middle band.
    """

    clear_below: float = 0.42
    escalate_at: float = 0.80
    critical_signals: frozenset = frozenset(
        {"merchant_burst_cross_card", "amount_vs_card_median"}
    )


DEFAULT_CONFIG = DecisionConfig()


@dataclass
class AiVerdict:
    """A Gemini (or other) second opinion for the borderline branch."""

    risk: str = "medium"          # "high" | "medium" | "low"
    confidence: float = 0.0       # 0..1
    rationale: str = ""

    @classmethod
    def from_obj(cls, obj) -> "AiVerdict | None":
        if obj is None:
            return None
        if isinstance(obj, AiVerdict):
            return obj
        return cls(
            risk=str(obj.get("risk", "medium")).lower(),
            confidence=float(obj.get("confidence", 0.0) or 0.0),
            rationale=str(obj.get("rationale", "")),
        )


@dataclass
class Decision:
    """The routing result. `trail` records which branch fired (explainability)."""

    action: str
    notify: bool = False
    trail: list[str] = field(default_factory=list)
    used_ai: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _score_of(record) -> float:
    if isinstance(record, dict):
        return float(record.get("fraud_score", 0.0) or 0.0)
    return float(getattr(record, "fraud_score", 0.0) or 0.0)


def _fired_signals(record) -> set[str]:
    reasons = record.get("reasons", []) if isinstance(record, dict) else getattr(record, "reasons", [])
    out: set[str] = set()
    for r in reasons or []:
        if isinstance(r, dict):
            sig = r.get("signal")
        else:
            sig = getattr(r, "signal", None)
        if sig:
            out.add(sig)
    return out


def route(record, ai_verdict=None, config: DecisionConfig = DEFAULT_CONFIG) -> Decision:
    """Run the tree over a scored record and return the operational Decision.

    The branches are evaluated top to bottom; the first match wins.
    """
    score = _score_of(record)
    fired = _fired_signals(record)
    verdict = AiVerdict.from_obj(ai_verdict)

    # Branch 1 — a critical signal fired: coordinated ring or extreme outlier.
    hit = fired & config.critical_signals
    if hit:
        sig = sorted(hit)[0]
        return Decision(
            action=ESCALATE,
            notify=True,
            trail=[f"critical signal fired: {sig}"],
            reason=f"Critical signal '{sig}' — escalated to analyst.",
        )

    # Branch 2 — high-confidence score.
    if score >= config.escalate_at:
        return Decision(
            action=ESCALATE,
            notify=True,
            trail=[f"score {score:.2f} >= escalate_at {config.escalate_at:.2f}"],
            reason=f"Score {score:.2f} above escalation threshold — escalated to analyst.",
        )

    # Branch 3 — clearly benign.
    if score < config.clear_below:
        return Decision(
            action=AUTO_CLEAR,
            notify=False,
            trail=[f"score {score:.2f} < clear_below {config.clear_below:.2f}"],
            reason=f"Score {score:.2f} below clear threshold — auto-cleared.",
        )

    # Branch 4 — borderline: consult AI if we have a verdict, else queue for a human.
    trail = [f"borderline: {config.clear_below:.2f} <= score {score:.2f} < {config.escalate_at:.2f}"]
    if verdict is not None:
        trail.append(f"AI verdict: {verdict.risk} (conf {verdict.confidence:.2f})")
        if verdict.risk == "high":
            return Decision(
                action=ESCALATE,
                notify=True,
                trail=trail,
                used_ai=True,
                reason=f"Borderline score, AI flagged high risk — escalated. {verdict.rationale}".strip(),
            )
        if verdict.risk == "low":
            return Decision(
                action=QUEUE,
                notify=False,
                trail=trail,
                used_ai=True,
                reason="Borderline score, AI judged low risk — sent to review queue.",
            )
        # medium / unknown -> fall through to human review.

    trail.append("no decisive AI verdict — defaulting to human review")
    return Decision(
        action=QUEUE,
        notify=False,
        trail=trail,
        used_ai=verdict is not None,
        reason="Borderline score — sent to the human review queue.",
    )
