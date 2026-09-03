"""
DriftGuard-X v2 — Policy Shadow / Simulation Mode
PRIVATE — All Rights Reserved.

Allows a candidate policy to be evaluated against historical run events
WITHOUT activating it. Produces a shadow report showing:
  - Which events would have been ALLOW / DENY / NEEDS_APPROVAL under new policy.
  - Diff against the decisions recorded under the currently active policy.
  - Summary statistics: # newly blocked, # newly allowed, # unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.policy.src.resolver import InheritanceResolver, PolicyRegistry


@dataclass
class HistoricalEvent:
    """A recorded policy decision from a past run."""

    event_id: str
    action: str
    tenant_id: str
    node_id: str
    requester_id: str
    requester_role: str
    recorded_verdict: str  # "allow" | "deny" | "needs_approval"
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ShadowResult:
    """Shadow evaluation result for a single historical event."""

    event_id: str
    action: str
    recorded_verdict: str
    shadow_verdict: str
    changed: bool
    change_direction: str | None  # "tightened" | "relaxed" | None
    shadow_rule_id: str
    shadow_rationale: str


@dataclass
class ShadowReport:
    """Full shadow evaluation report for a candidate policy."""

    candidate_policy_id: str
    n_events: int
    n_unchanged: int
    n_tightened: int  # events that would be more restricted
    n_relaxed: int  # events that would be less restricted (flag for review)
    results: list[ShadowResult]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def summary(self) -> str:
        return (
            f"Shadow Report [{self.candidate_policy_id}]\n"
            f"  Events evaluated : {self.n_events}\n"
            f"  Unchanged        : {self.n_unchanged}\n"
            f"  Tightened        : {self.n_tightened}\n"
            f"  Relaxed          : {self.n_relaxed}  ← REVIEW REQUIRED\n"
        )


def shadow_evaluate(
    events: list[HistoricalEvent],
    candidate_registry: PolicyRegistry,
    candidate_policy_id: str = "candidate",
) -> ShadowReport:
    """
    Evaluate a list of historical events against a candidate policy registry.
    Returns a ShadowReport without activating the candidate policy.
    """
    resolver = InheritanceResolver(candidate_registry)
    results: list[ShadowResult] = []
    n_unchanged = n_tightened = n_relaxed = 0

    _VERDICT_RANK = {
        "allow": 2,
        "needs_approval": 1,
        "deny": 0,
    }

    for ev in events:
        try:
            ep = resolver.resolve(ev.tenant_id, ev.node_id, ev.action, ev.requester_role)
            shadow_verdict = ep.verdict.value
            shadow_rule_id = ep.winning_rule.rule_id
            shadow_rationale = ep.winning_rule.rationale
        except Exception as exc:
            shadow_verdict = "deny"
            shadow_rule_id = "SHADOW_ERROR"
            shadow_rationale = str(exc)

        recorded_rank = _VERDICT_RANK.get(ev.recorded_verdict, 2)
        shadow_rank = _VERDICT_RANK.get(shadow_verdict, 2)

        changed = shadow_verdict != ev.recorded_verdict
        if not changed:
            change_direction = None
            n_unchanged += 1
        elif shadow_rank < recorded_rank:
            change_direction = "tightened"
            n_tightened += 1
        else:
            change_direction = "relaxed"
            n_relaxed += 1

        results.append(
            ShadowResult(
                event_id=ev.event_id,
                action=ev.action,
                recorded_verdict=ev.recorded_verdict,
                shadow_verdict=shadow_verdict,
                changed=changed,
                change_direction=change_direction,
                shadow_rule_id=shadow_rule_id,
                shadow_rationale=shadow_rationale,
            )
        )

    return ShadowReport(
        candidate_policy_id=candidate_policy_id,
        n_events=len(events),
        n_unchanged=n_unchanged,
        n_tightened=n_tightened,
        n_relaxed=n_relaxed,
        results=results,
    )
