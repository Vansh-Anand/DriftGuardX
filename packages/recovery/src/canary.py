"""
DriftGuard-X v2 — Canary Verification
PRIVATE — All Rights Reserved.

After a recovery action executes, a bounded canary replay set is used to
verify that the action improved (or at least did not worsen) the pipeline's
safety, quality, cost, and latency metrics.

Canary design:
  - A small, representative replay set (N ≤ 50 episodes by default).
  - Metrics are compared: baseline (pre-action) vs. post-action.
  - Verification passes when ALL of:
      safety_delta  >= 0          (safety never decreases)
      quality_delta >= QUALITY_THRESHOLD  (configurable, default -0.02)
      cost_delta    <= COST_THRESHOLD     (configurable, default +0.20 USD)
      latency_delta <= LATENCY_THRESHOLD  (configurable, default +200 ms)
  - Partial improvement is reported but does NOT auto-commit: only when
    ALL thresholds pass does VERIFYING → COMMITTED fire.
  - If verification fails and policy allows, COMPENSATING fires automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class CanaryEpisode:
    """One canary replay episode with baseline and post-action metrics."""
    episode_id: str
    baseline_quality: float     # 0–1
    baseline_cost_usd: float
    baseline_latency_ms: float
    baseline_safe: bool         # True = no safety violation
    post_quality: float
    post_cost_usd: float
    post_latency_ms: float
    post_safe: bool


@dataclass
class CanaryThresholds:
    min_quality_delta: float = -0.02    # quality may drop by at most 2%
    max_cost_delta_usd: float = 0.20    # cost may increase by at most $0.20
    max_latency_delta_ms: float = 200.0 # latency may increase by at most 200ms


@dataclass
class CanaryVerificationResult:
    """Verification outcome for the canary replay set."""
    proposal_id: str
    n_episodes: int
    safety_pass: bool
    quality_pass: bool
    cost_pass: bool
    latency_pass: bool
    overall_pass: bool

    mean_quality_delta: float
    mean_cost_delta: float
    mean_latency_delta: float
    safety_violations_post: int

    failure_reasons: List[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        icon = "✓" if self.overall_pass else "✗"
        return (
            f"[{icon}] Canary ({self.n_episodes} eps): "
            f"safety={'OK' if self.safety_pass else 'FAIL'} "
            f"quality={'OK' if self.quality_pass else 'FAIL'} ({self.mean_quality_delta:+.3f}) "
            f"cost={'OK' if self.cost_pass else 'FAIL'} ({self.mean_cost_delta:+.3f}$) "
            f"latency={'OK' if self.latency_pass else 'FAIL'} ({self.mean_latency_delta:+.1f}ms)"
        )


def run_canary_verification(
    proposal_id: str,
    episodes: List[CanaryEpisode],
    thresholds: Optional[CanaryThresholds] = None,
) -> CanaryVerificationResult:
    """
    Run canary verification on a list of episodes.
    Returns a CanaryVerificationResult (never raises).
    """
    if thresholds is None:
        thresholds = CanaryThresholds()

    if not episodes:
        return CanaryVerificationResult(
            proposal_id=proposal_id, n_episodes=0,
            safety_pass=False, quality_pass=False, cost_pass=False, latency_pass=False,
            overall_pass=False,
            mean_quality_delta=0.0, mean_cost_delta=0.0, mean_latency_delta=0.0,
            safety_violations_post=0,
            failure_reasons=["No canary episodes provided."],
        )

    n = len(episodes)
    quality_deltas = [ep.post_quality - ep.baseline_quality for ep in episodes]
    cost_deltas    = [ep.post_cost_usd - ep.baseline_cost_usd for ep in episodes]
    latency_deltas = [ep.post_latency_ms - ep.baseline_latency_ms for ep in episodes]
    safety_violations_post = sum(1 for ep in episodes if not ep.post_safe)

    mean_q = sum(quality_deltas) / n
    mean_c = sum(cost_deltas) / n
    mean_l = sum(latency_deltas) / n

    # Safety: must never introduce new violations
    baseline_violations = sum(1 for ep in episodes if not ep.baseline_safe)
    safety_pass = safety_violations_post <= baseline_violations

    quality_pass  = mean_q >= thresholds.min_quality_delta
    cost_pass     = mean_c <= thresholds.max_cost_delta_usd
    latency_pass  = mean_l <= thresholds.max_latency_delta_ms

    failure_reasons = []
    if not safety_pass:
        failure_reasons.append(
            f"Safety regression: {safety_violations_post} post-action violations "
            f"vs {baseline_violations} baseline."
        )
    if not quality_pass:
        failure_reasons.append(
            f"Quality regression: mean delta {mean_q:+.3f} < threshold {thresholds.min_quality_delta}."
        )
    if not cost_pass:
        failure_reasons.append(
            f"Cost overrun: mean delta +${mean_c:.3f} > threshold +${thresholds.max_cost_delta_usd}."
        )
    if not latency_pass:
        failure_reasons.append(
            f"Latency regression: mean delta +{mean_l:.1f}ms > threshold +{thresholds.max_latency_delta_ms}ms."
        )

    overall_pass = safety_pass and quality_pass and cost_pass and latency_pass

    return CanaryVerificationResult(
        proposal_id=proposal_id,
        n_episodes=n,
        safety_pass=safety_pass,
        quality_pass=quality_pass,
        cost_pass=cost_pass,
        latency_pass=latency_pass,
        overall_pass=overall_pass,
        mean_quality_delta=mean_q,
        mean_cost_delta=mean_c,
        mean_latency_delta=mean_l,
        safety_violations_post=safety_violations_post,
        failure_reasons=failure_reasons,
    )
