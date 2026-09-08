"""
DriftGuard-X v2 — Confidence Bound Library
PRIVATE — All Rights Reserved.

Implements analytic and empirical confidence bounds with explicit assumption
documentation. Returns UnsupportedBound when assumptions are violated rather
than manufacturing a number.

Statistical Assumptions Documented
===================================
Hoeffding Bound:
  - Rewards bounded in [a, b] (here normalised to [0, 1]).
  - Samples are i.i.d. or satisfy a martingale difference condition.
  - The finite-sample inequality needs no asymptotic approximation. Below 30
    observations the result carries a conservative-width warning.
  - Fixed-sample inference assumes independent bounded observations. This
    function does not implement an anytime-valid adaptive stopping correction.

Bootstrap Bound:
  - Distribution-free: no shape assumption on rewards.
  - Requires n >= MIN_N_BOOTSTRAP (10) to form a meaningful resample
    distribution.
  - Each draw treated as exchangeable; if sampling was adaptive, coverage is
    approximate.

Conformal Interval:
  - Requires a *separate* calibration split never used for arm selection.
  - Coverage is conditional on held-out, exchangeable calibration residuals.
    The caller must establish those assumptions; numeric values cannot do so.
  - Does not require reward boundedness.

UnsupportedBound:
  - Returned whenever none of the above assumptions can be satisfied given the
    provided data. Callers must treat this as an uncertified result.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Literal

# ─── Thresholds ──────────────────────────────────────────────────────────────
MIN_N_HOEFFDING = 30  # below this we flag low-n but still return
MIN_N_BOOTSTRAP = 10  # below this we return UnsupportedBound
N_BOOTSTRAP_RESAMPLES = 2000

# ─── Result Dataclass ─────────────────────────────────────────────────────────


@dataclass
class BoundResult:
    """
    A single confidence bound result.

    Attributes
    ----------
    method:           Which calculator produced this result.
    is_supported:     False → assumptions violated; treat as UNCERTIFIED.
    lower:            Lower end of the confidence interval (None if unsupported).
    upper:            Upper end of the confidence interval (None if unsupported).
    point_estimate:   Sample mean of the reward observations.
    nominal_confidence: Requested confidence level (e.g. 0.90).
    n:                Number of observations used.
    assumptions_met:  Human-readable list of satisfied assumptions.
    assumptions_violated: Human-readable list of violated or untestable assumptions.
    warning:          Optional free-text warning (e.g. low-n).
    epsilon:          Half-width of the interval (upper - point_estimate), or None.
    delta:            Failure probability = 1 - nominal_confidence, or None.
    """

    method: Literal["hoeffding", "bootstrap", "conformal", "unsupported"]
    is_supported: bool
    point_estimate: float
    nominal_confidence: float
    n: int
    assumptions_met: list[str] = field(default_factory=list)
    assumptions_violated: list[str] = field(default_factory=list)
    lower: float | None = None
    upper: float | None = None
    epsilon: float | None = None
    delta: float | None = None
    warning: str | None = None


# ─── Unsupported Sentinel ─────────────────────────────────────────────────────


def unsupported_bound(
    observations: list[float],
    nominal_confidence: float,
    reason: str,
) -> BoundResult:
    n = len(observations)
    mean = sum(x / n for x in observations) if n and all(map(math.isfinite, observations)) else 0.0
    return BoundResult(
        method="unsupported",
        is_supported=False,
        point_estimate=mean,
        nominal_confidence=nominal_confidence,
        n=n,
        assumptions_violated=[reason],
        warning=f"Bound not computed: {reason}",
    )


# ─── Hoeffding Analytic Bound ─────────────────────────────────────────────────


def _input_error(observations: list[float], confidence: float) -> str | None:
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        return "Confidence must be finite and strictly between zero and one."
    if not all(map(math.isfinite, observations)):
        return "All observations must be finite."
    return None


def hoeffding_bound(
    observations: list[float],
    nominal_confidence: float = 0.90,
    reward_min: float = 0.0,
    reward_max: float = 1.0,
) -> BoundResult:
    """
    Hoeffding's inequality: P(|X̄ - μ| ≥ ε) ≤ 2·exp(-2nε²/(b-a)²)
    Solving for ε at confidence level (1-δ):
        ε = (b-a) · sqrt(ln(2/δ) / (2n))

    Assumptions checked:
      1. All observations are in [reward_min, reward_max].
      2. n >= MIN_N_HOEFFDING (soft warning below, still valid above n >= 1).
      3. reward_max > reward_min (non-degenerate range).
    """
    n = len(observations)

    error = _input_error(observations, nominal_confidence)
    if error:
        return unsupported_bound(observations, nominal_confidence, error)
    if not all(map(math.isfinite, (reward_min, reward_max, reward_max - reward_min))):
        return unsupported_bound(observations, nominal_confidence, "Reward range must be finite.")

    if n == 0:
        return unsupported_bound(observations, nominal_confidence, "No observations provided.")

    if reward_max <= reward_min:
        return unsupported_bound(
            observations,
            nominal_confidence,
            f"Degenerate reward range: [{reward_min}, {reward_max}]",
        )

    assumptions_met = []
    assumptions_violated: list[str] = []
    warning = None

    # Check boundedness
    out_of_range = [x for x in observations if x < reward_min or x > reward_max]
    if out_of_range:
        return unsupported_bound(
            observations,
            nominal_confidence,
            f"{len(out_of_range)} observations fall outside [{reward_min}, {reward_max}]; "
            "Hoeffding boundedness assumption violated.",
        )
    assumptions_met.append(f"All {n} rewards in [{reward_min}, {reward_max}].")

    if n < MIN_N_HOEFFDING:
        warning = (
            f"n={n} < {MIN_N_HOEFFDING}: Hoeffding bound is valid but conservative; "
            "consider collecting more episodes."
        )
    else:
        assumptions_met.append(f"n={n} >= {MIN_N_HOEFFDING} (low-n threshold).")

    assumptions_met.append(
        "Independent bounded observations assumed by caller; fixed sample size. "
        "No adaptive stopping or multiple-comparison correction is applied."
    )

    # Compute ε
    delta = 1.0 - nominal_confidence
    range_width = reward_max - reward_min
    epsilon = range_width * math.sqrt(math.log(2.0 / delta) / (2.0 * n))

    mean = sum(x / n for x in observations)
    lower = max(reward_min, mean - epsilon)
    upper = min(reward_max, mean + epsilon)

    return BoundResult(
        method="hoeffding",
        is_supported=True,
        point_estimate=mean,
        nominal_confidence=nominal_confidence,
        n=n,
        assumptions_met=assumptions_met,
        assumptions_violated=assumptions_violated,
        lower=lower,
        upper=upper,
        epsilon=epsilon,
        delta=delta,
        warning=warning,
    )


# ─── Bootstrap Empirical Bound ────────────────────────────────────────────────


def bootstrap_bound(
    observations: list[float],
    nominal_confidence: float = 0.90,
    n_resamples: int = N_BOOTSTRAP_RESAMPLES,
    seed: int = 42,
) -> BoundResult:
    """
    Percentile bootstrap confidence interval.
    Distribution-free; requires n >= MIN_N_BOOTSTRAP.

    Assumptions:
      1. n >= MIN_N_BOOTSTRAP.
      2. Observations are exchangeable (approximately i.i.d.).
    """
    n = len(observations)

    error = _input_error(observations, nominal_confidence)
    if error:
        return unsupported_bound(observations, nominal_confidence, error)
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 1:
        return unsupported_bound(
            observations, nominal_confidence, "Resamples must be a positive integer."
        )

    if n < MIN_N_BOOTSTRAP:
        return unsupported_bound(
            observations,
            nominal_confidence,
            f"n={n} < {MIN_N_BOOTSTRAP}: insufficient data for bootstrap resampling.",
        )

    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(n_resamples):
        resample = [rng.choice(observations) for _ in range(n)]
        boot_means.append(sum(x / n for x in resample))

    boot_means.sort()
    alpha = 1.0 - nominal_confidence
    lo_idx = int(math.floor(alpha / 2 * n_resamples))
    hi_idx = int(math.ceil((1.0 - alpha / 2) * n_resamples)) - 1
    lo_idx = max(0, lo_idx)
    hi_idx = min(n_resamples - 1, hi_idx)

    mean = sum(x / n for x in observations)
    lower = boot_means[lo_idx]
    upper = boot_means[hi_idx]
    epsilon = (upper - lower) / 2.0

    return BoundResult(
        method="bootstrap",
        is_supported=True,
        point_estimate=mean,
        nominal_confidence=nominal_confidence,
        n=n,
        assumptions_met=[
            f"n={n} >= {MIN_N_BOOTSTRAP} (bootstrap minimum).",
            "Distribution-free; no shape assumption on reward distribution.",
            "Observations treated as exchangeable.",
        ],
        lower=lower,
        upper=upper,
        epsilon=epsilon,
        delta=1.0 - nominal_confidence,
    )


# ─── Conformal Prediction Interval ───────────────────────────────────────────


def conformal_bound(
    calibration_scores: list[float],
    new_score: float,
    nominal_confidence: float = 0.90,
) -> BoundResult:
    """
    Split-conformal prediction interval using nonconformity scores.
    Marginal coverage guarantee (1 - alpha) when calibration is i.i.d. with test.

    calibration_scores: held-out nonconformity scores (e.g. |predicted - actual|).
    new_score:          the prediction center in the original target space.

    Returns a threshold τ such that P(score <= τ) >= nominal_confidence.
    The interval is [new_score - τ, new_score + τ] in the original space.

    Assumptions:
      1. Calibration set is separate from training / arm-selection data.
      2. Calibration + test scores are exchangeable.
      3. |calibration_scores| >= 10.
    """
    n_cal = len(calibration_scores)

    error = _input_error(calibration_scores, nominal_confidence)
    if error:
        return unsupported_bound(calibration_scores, nominal_confidence, error)
    if not math.isfinite(new_score) or any(x < 0 for x in calibration_scores):
        return unsupported_bound(
            calibration_scores,
            nominal_confidence,
            "Prediction center must be finite and absolute residuals nonnegative.",
        )

    if n_cal < 10:
        return unsupported_bound(
            calibration_scores,
            nominal_confidence,
            f"Calibration set has only {n_cal} scores; need >= 10 for conformal guarantee.",
        )

    alpha = 1.0 - nominal_confidence
    # A rank beyond n requires an infinite interval, never a clamped finite one.
    rank = math.ceil((n_cal + 1) * nominal_confidence)
    if rank > n_cal:
        return unsupported_bound(
            calibration_scores,
            nominal_confidence,
            "Calibration size cannot support a finite interval at this confidence.",
        )
    tau = sorted(calibration_scores)[rank - 1]
    lower = new_score - tau
    upper = new_score + tau
    if not math.isfinite(lower) or not math.isfinite(upper):
        return unsupported_bound(calibration_scores, nominal_confidence, "Interval overflow.")

    return BoundResult(
        method="conformal",
        is_supported=True,
        point_estimate=new_score,
        nominal_confidence=nominal_confidence,
        n=n_cal,
        assumptions_met=[
            f"Calibration set size n_cal={n_cal} >= 10.",
            "Caller must supply a separate calibration split unused in fitting or arm selection.",
            "Coverage is conditional on exchangeability; not verified from numeric inputs.",
        ],
        lower=lower,
        upper=upper,
        epsilon=tau,
        delta=alpha,
    )
