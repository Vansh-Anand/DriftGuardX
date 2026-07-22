"""
DriftGuard-X v2 — Calibration Pipeline
PRIVATE — All Rights Reserved.

Measures empirical coverage of confidence intervals against a held-out
calibration dataset that is separate from the arm-selection / development
episodes. Calibration episodes are (predicted_interval, ground_truth_reward)
pairs collected from the fault-injection lab.

Coverage is measured at nominal levels [0.80, 0.90, 0.95, 0.99] and compared
to observed fractions.  An UndercoverageAlert is issued when the gap between
nominal and observed coverage exceeds MAX_UNDERCOVERAGE_GAP.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple, Dict


# ─── Constants ────────────────────────────────────────────────────────────────
NOMINAL_LEVELS = [0.80, 0.90, 0.95, 0.99]
MAX_UNDERCOVERAGE_GAP = 0.05   # alert if empirical < nominal - gap
MIN_CAL_EPISODES = 20          # minimum calibration episodes for a valid report
CALIBRATION_SCHEMA_VERSION = "v1.0"


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class CalibrationEpisode:
    """
    One calibration record: the CI that was issued and the true outcome.

    lower / upper: the confidence interval bounds that were issued.
    ground_truth:  the true reward / diagnostic accuracy observed ex-post.
    fault_type:    optional tag for subgroup analysis.
    component_layer: optional tag for subgroup analysis.
    """
    lower: float
    upper: float
    ground_truth: float
    fault_type: str = "unknown"
    component_layer: str = "unknown"
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UndercoverageAlert:
    nominal_confidence: float
    observed_coverage: float
    gap: float
    n_episodes: int
    message: str


@dataclass
class CoverageReport:
    schema_version: str
    n_episodes: int
    is_valid: bool                          # False if n < MIN_CAL_EPISODES
    coverage_by_level: Dict[float, float]   # nominal -> observed
    alerts: List[UndercoverageAlert]
    subgroup_coverage: Dict[str, Dict[float, float]]  # group -> nominal -> observed
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Calibration Dataset ──────────────────────────────────────────────────────

class CalibrationDataset:
    """
    Versioned, append-only calibration dataset.
    In production this would persist to the BanditState table; here we keep
    an in-memory list for local / test use.
    """

    def __init__(self, version: str = CALIBRATION_SCHEMA_VERSION):
        self.version = version
        self._episodes: List[CalibrationEpisode] = []

    def add(self, episode: CalibrationEpisode) -> None:
        self._episodes.append(episode)

    def episodes(self) -> List[CalibrationEpisode]:
        return list(self._episodes)

    def __len__(self) -> int:
        return len(self._episodes)


# ─── Coverage Calculator ──────────────────────────────────────────────────────

def _coverage_for_level(
    episodes: List[CalibrationEpisode],
    nominal: float,
) -> float:
    """
    Empirical coverage: fraction of episodes where ground_truth ∈ [lower, upper].
    The bounds stored in the episode were computed at *this* nominal level.
    This function simply checks containment; interval width varies by method.
    """
    if not episodes:
        return 0.0
    hits = sum(1 for ep in episodes if ep.lower <= ep.ground_truth <= ep.upper)
    return hits / len(episodes)


def measure_coverage(dataset: CalibrationDataset) -> CoverageReport:
    """
    Compute empirical coverage at all nominal levels and produce a CoverageReport.
    Subgroup coverage is broken down by fault_type and component_layer.
    """
    episodes = dataset.episodes()
    n = len(episodes)
    is_valid = n >= MIN_CAL_EPISODES

    coverage_by_level: Dict[float, float] = {}
    alerts: List[UndercoverageAlert] = []

    for level in NOMINAL_LEVELS:
        obs = _coverage_for_level(episodes, level)
        coverage_by_level[level] = obs
        gap = level - obs
        if gap > MAX_UNDERCOVERAGE_GAP:
            alerts.append(UndercoverageAlert(
                nominal_confidence=level,
                observed_coverage=obs,
                gap=gap,
                n_episodes=n,
                message=(
                    f"Undercoverage at {level*100:.0f}%: "
                    f"observed={obs:.3f}, gap={gap:.3f} > threshold={MAX_UNDERCOVERAGE_GAP}"
                ),
            ))

    # Subgroup analysis by fault_type
    subgroup_coverage: Dict[str, Dict[float, float]] = {}
    fault_types = {ep.fault_type for ep in episodes}
    for ft in fault_types:
        sub = [ep for ep in episodes if ep.fault_type == ft]
        subgroup_coverage[f"fault:{ft}"] = {
            level: _coverage_for_level(sub, level) for level in NOMINAL_LEVELS
        }

    # Subgroup analysis by component_layer
    layers = {ep.component_layer for ep in episodes}
    for layer in layers:
        sub = [ep for ep in episodes if ep.component_layer == layer]
        subgroup_coverage[f"layer:{layer}"] = {
            level: _coverage_for_level(sub, level) for level in NOMINAL_LEVELS
        }

    return CoverageReport(
        schema_version=CALIBRATION_SCHEMA_VERSION,
        n_episodes=n,
        is_valid=is_valid,
        coverage_by_level=coverage_by_level,
        alerts=alerts,
        subgroup_coverage=subgroup_coverage,
    )


# ─── Conformal Calibration Baseline ──────────────────────────────────────────

def conformal_coverage_check(
    calibration_scores: List[float],
    test_scores: List[float],
    nominal_confidence: float = 0.90,
) -> Tuple[float, bool]:
    """
    Marginal coverage check for a conformal predictor.

    Returns (observed_coverage, meets_guarantee).
    The conformal guarantee is that observed_coverage >= nominal_confidence
    up to 1/n_cal slack.
    """
    if not calibration_scores or not test_scores:
        return 0.0, False

    n_cal = len(calibration_scores)
    alpha = 1.0 - nominal_confidence
    q_level = math.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal
    q_level = min(q_level, 1.0)

    sorted_cal = sorted(calibration_scores)
    q_idx = min(int(math.floor(q_level * n_cal)), n_cal - 1)
    tau = sorted_cal[q_idx]

    covered = sum(1 for s in test_scores if s <= tau)
    observed = covered / len(test_scores)
    # Theoretical guarantee: observed >= nominal - 1/n_cal with high probability
    slack = 1.0 / n_cal
    return observed, observed >= nominal_confidence - slack
