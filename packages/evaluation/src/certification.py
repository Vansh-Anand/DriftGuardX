"""
DriftGuard-X v2 — Certification Policy
PRIVATE — All Rights Reserved.

A diagnosis may receive one of three verdicts:

  CERTIFIED   — All gates pass. Downstream automation is allowed.
  UNCERTIFIED — One or more soft gates failed. A diagnosis is returned but
                ALL consequential actions require explicit human approval.
  REJECTED    — Critical assumptions violated or calibration expired.
                Automated downstream actions are BLOCKED.

This module implements the gate checks and returns a structured
CertificationDecision.  Policy parameters are versioned and must not be
changed without bumping POLICY_VERSION.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from packages.evaluation.src.bounds import BoundResult

# ─── Policy Version ───────────────────────────────────────────────────────────
POLICY_VERSION = "v1.0"

CertStatus = Literal["CERTIFIED", "UNCERTIFIED", "REJECTED"]


@dataclass
class CertificationPolicy:
    """
    Versioned certification policy.  Change any field → bump policy_version.
    """

    policy_version: str = POLICY_VERSION
    min_episodes: int = 10
    min_valid_replay_fraction: float = 0.5
    max_calibration_age_days: int = 30
    target_nominal_confidence: float = 0.90
    max_undercoverage_allowed: float = 0.05


@dataclass
class CertificationDecision:
    """
    Structured certification verdict with machine-readable fields.
    All failing gates are recorded; callers must not suppress them.
    """

    status: CertStatus
    policy_version: str
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    human_review_required: bool = False
    block_automated_action: bool = False
    reason: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ─── Gate Checks ──────────────────────────────────────────────────────────────


def _check_episode_count(n_episodes: int, policy: CertificationPolicy) -> tuple[bool, str]:
    ok = n_episodes >= policy.min_episodes
    msg = (
        f"episode_count: n={n_episodes} >= {policy.min_episodes}"
        if ok
        else f"episode_count: n={n_episodes} < {policy.min_episodes} required"
    )
    return ok, msg


def _check_valid_replay_fraction(
    valid_replays: int,
    total_replays: int,
    policy: CertificationPolicy,
) -> tuple[bool, str]:
    if total_replays == 0:
        return False, "valid_replay_fraction: no replays recorded — REJECTED"
    fraction = valid_replays / total_replays
    ok = fraction >= policy.min_valid_replay_fraction
    msg = (
        f"valid_replay_fraction: {fraction:.2f} >= {policy.min_valid_replay_fraction}"
        if ok
        else f"valid_replay_fraction: {fraction:.2f} < {policy.min_valid_replay_fraction}"
    )
    return ok, msg


def _check_calibration_age(
    last_calibrated_at: datetime | None,
    policy: CertificationPolicy,
) -> tuple[bool, str]:
    if last_calibrated_at is None:
        return False, "calibration_age: no calibration dataset found — UNCERTIFIED"
    now = datetime.now(UTC)
    age_days = (now - last_calibrated_at).total_seconds() / 86400
    ok = age_days <= policy.max_calibration_age_days
    msg = (
        f"calibration_age: {age_days:.1f}d <= {policy.max_calibration_age_days}d"
        if ok
        else f"calibration_age: {age_days:.1f}d > {policy.max_calibration_age_days}d (expired)"
    )
    return ok, msg


def _check_bound_supported(bound: BoundResult) -> tuple[bool, str]:
    ok = bound.is_supported
    msg = (
        f"bound_assumptions: method={bound.method}, supported=True"
        if ok
        else f"bound_assumptions: method={bound.method}, supported=False — {bound.warning}"
    )
    return ok, msg


def _check_empirical_coverage(
    observed_coverage: float | None,
    nominal_confidence: float,
    max_undercoverage: float,
) -> tuple[bool, str]:
    if observed_coverage is None:
        return False, "empirical_coverage: not measured — UNCERTIFIED"
    gap = nominal_confidence - observed_coverage
    ok = gap <= max_undercoverage
    msg = (
        f"empirical_coverage: observed={observed_coverage:.3f}, "
        f"nominal={nominal_confidence:.2f}, gap={gap:.3f} <= {max_undercoverage}"
        if ok
        else f"empirical_coverage: UNDERCOVERAGE observed={observed_coverage:.3f}, "
        f"nominal={nominal_confidence:.2f}, gap={gap:.3f} > {max_undercoverage}"
    )
    return ok, msg


# ─── Main Certifier ───────────────────────────────────────────────────────────


def certify(
    *,
    bound: BoundResult,
    n_episodes: int,
    valid_replays: int,
    total_replays: int,
    last_calibrated_at: datetime | None,
    observed_coverage: float | None,
    policy: CertificationPolicy | None = None,
) -> CertificationDecision:
    """
    Run all certification gates and return a CertificationDecision.

    Critical failures (total_replays == 0 or bound not supported) → REJECTED.
    Non-critical failures → UNCERTIFIED with human review required.
    All gates pass → CERTIFIED.
    """
    if policy is None:
        policy = CertificationPolicy()

    gates_passed: list[str] = []
    gates_failed: list[str] = []
    critical_failure = False

    # ── Gate 1: Bound assumptions ─────────────────────────────────────────────
    ok, msg = _check_bound_supported(bound)
    (gates_passed if ok else gates_failed).append(msg)

    # ── Gate 2: Episode count ─────────────────────────────────────────────────
    ok2, msg2 = _check_episode_count(n_episodes, policy)
    (gates_passed if ok2 else gates_failed).append(msg2)

    # ── Gate 3: Valid replay fraction ─────────────────────────────────────────
    ok3, msg3 = _check_valid_replay_fraction(valid_replays, total_replays, policy)
    (gates_passed if ok3 else gates_failed).append(msg3)
    if total_replays == 0:
        critical_failure = True

    # ── Gate 4: Calibration age ───────────────────────────────────────────────
    ok4, msg4 = _check_calibration_age(last_calibrated_at, policy)
    (gates_passed if ok4 else gates_failed).append(msg4)

    # ── Gate 5: Empirical coverage ────────────────────────────────────────────
    ok5, msg5 = _check_empirical_coverage(
        observed_coverage, policy.target_nominal_confidence, policy.max_undercoverage_allowed
    )
    (gates_passed if ok5 else gates_failed).append(msg5)

    # ── Verdict ───────────────────────────────────────────────────────────────
    if critical_failure or not ok:  # no replays or bound unsupported → REJECTED
        status: CertStatus = "REJECTED"
        block = True
        review = True
        reason = "Critical gate failure: " + "; ".join(gates_failed)
    elif gates_failed:
        status = "UNCERTIFIED"
        block = False
        review = True
        reason = "Soft gate failure(s): " + "; ".join(gates_failed)
    else:
        status = "CERTIFIED"
        block = False
        review = False
        reason = "All certification gates passed."

    return CertificationDecision(
        status=status,
        policy_version=policy.policy_version,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        human_review_required=review,
        block_automated_action=block,
        reason=reason,
    )
