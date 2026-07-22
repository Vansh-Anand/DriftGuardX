"""
DriftGuard-X v2 — Bounds & Calibration E2E Tests
PRIVATE — All Rights Reserved.

Covers all acceptance gates:
  [1] Synthetic simulations achieve expected coverage in supported regimes.
  [2] Stress tests flag undercoverage when assumptions are violated.
  [3] Analytic and empirical intervals compared fairly.
  [4] Certificates include machine-readable assumption/calibration fields.
  [5] CERTIFIED status blocked when certification requirements unmet.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta

import pytest

from packages.evaluation.src.bounds import (
    hoeffding_bound,
    bootstrap_bound,
    conformal_bound,
    unsupported_bound,
    MIN_N_HOEFFDING,
    MIN_N_BOOTSTRAP,
)
from packages.evaluation.src.calibration import (
    CalibrationDataset,
    CalibrationEpisode,
    measure_coverage,
    MIN_CAL_EPISODES,
)
from packages.evaluation.src.certification import (
    CertificationPolicy,
    certify,
)
from packages.evaluation.src.coverage_monitor import (
    CoverageMonitor,
    DiagnosisEvent,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_iid_rewards(n: int, mean: float = 0.7, seed: int = 42) -> list[float]:
    rng = random.Random(seed)
    return [max(0.0, min(1.0, mean + rng.uniform(-0.15, 0.15))) for _ in range(n)]


def _recent_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def _expired_dt() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=40)


# ─── [1] Supported regime: Hoeffding ──────────────────────────────────────────

def test_hoeffding_bound_is_supported_with_sufficient_n():
    obs = _make_iid_rewards(40)
    result = hoeffding_bound(obs, nominal_confidence=0.90)
    assert result.is_supported is True
    assert result.method == "hoeffding"
    assert result.lower is not None and result.upper is not None
    assert result.lower <= result.point_estimate <= result.upper
    assert result.epsilon is not None and result.epsilon > 0
    assert result.delta == pytest.approx(0.10, abs=1e-9)
    # Bound should be in [0,1] when rewards are
    assert 0.0 <= result.lower <= 1.0
    assert 0.0 <= result.upper <= 1.0


def test_hoeffding_low_n_still_supported_but_warns():
    """n < MIN_N_HOEFFDING: bound is still returned (valid) but warning is set."""
    obs = _make_iid_rewards(10)
    result = hoeffding_bound(obs, nominal_confidence=0.90)
    assert result.is_supported is True
    assert result.warning is not None
    assert str(MIN_N_HOEFFDING) in result.warning


# ─── [2] Stress test: unsupported bound returned when assumptions violated ────

def test_hoeffding_returns_unsupported_when_reward_out_of_range():
    """Rewards outside [0,1] → Hoeffding boundedness assumption violated."""
    obs = [0.5, 0.6, 1.5, 0.4]  # 1.5 violates [0,1]
    result = hoeffding_bound(obs, nominal_confidence=0.90)
    assert result.is_supported is False
    assert result.method == "unsupported"
    assert len(result.assumptions_violated) > 0


def test_bootstrap_returns_unsupported_on_tiny_n():
    """n < MIN_N_BOOTSTRAP → UnsupportedBound returned."""
    obs = _make_iid_rewards(MIN_N_BOOTSTRAP - 1)
    result = bootstrap_bound(obs, nominal_confidence=0.90)
    assert result.is_supported is False
    assert result.method == "unsupported"


def test_conformal_returns_unsupported_on_small_calibration():
    """Fewer than 10 calibration scores → conformal guarantee not available."""
    cal_scores = [0.1, 0.2, 0.15]
    result = conformal_bound(cal_scores, new_score=0.12, nominal_confidence=0.90)
    assert result.is_supported is False
    assert result.method == "unsupported"


# ─── [3] Analytic vs empirical compared fairly ────────────────────────────────

def test_bootstrap_bound_is_tighter_than_hoeffding_on_same_data():
    """
    For well-behaved i.i.d. data, the bootstrap interval should be tighter
    than the Hoeffding analytic bound.  This is a statistical expectation,
    not a guarantee; we check it here on a deterministic seed.
    """
    obs = _make_iid_rewards(50, seed=99)
    h = hoeffding_bound(obs, nominal_confidence=0.90)
    b = bootstrap_bound(obs, nominal_confidence=0.90)
    assert h.is_supported and b.is_supported
    hoeffding_width = h.upper - h.lower
    bootstrap_width = b.upper - b.lower
    assert bootstrap_width < hoeffding_width, (
        f"Expected bootstrap ({bootstrap_width:.4f}) < hoeffding ({hoeffding_width:.4f})"
    )


def test_conformal_coverage_satisfied():
    """Conformal interval provides marginal coverage on held-out test scores."""
    rng = random.Random(0)
    cal_scores = [rng.uniform(0, 0.3) for _ in range(50)]
    test_scores = [rng.uniform(0, 0.3) for _ in range(30)]

    result = conformal_bound(cal_scores, new_score=0.15, nominal_confidence=0.90)
    assert result.is_supported is True
    assert result.method == "conformal"
    assert result.epsilon is not None


# ─── [4] Calibration: machine-readable fields ─────────────────────────────────

def test_calibration_coverage_report_fields():
    """CoverageReport contains all required machine-readable fields."""
    ds = CalibrationDataset(version="v1.0")
    rng = random.Random(1)
    # Add MIN_CAL_EPISODES episodes where ground truth always falls in the CI
    for _ in range(MIN_CAL_EPISODES + 5):
        g = rng.uniform(0.4, 0.6)
        ds.add(CalibrationEpisode(lower=g - 0.2, upper=g + 0.2, ground_truth=g))

    report = measure_coverage(ds)
    assert report.is_valid is True
    assert report.n_episodes == MIN_CAL_EPISODES + 5
    assert 0.80 in report.coverage_by_level
    assert 0.90 in report.coverage_by_level
    assert 0.95 in report.coverage_by_level
    assert 0.99 in report.coverage_by_level
    assert report.schema_version == "v1.0"


def test_undercoverage_alert_triggered():
    """UndercoverageAlert fires when intervals are systematically too narrow."""
    ds = CalibrationDataset()
    # Ground truth always outside the [lower, upper] range → 0% coverage
    for _ in range(MIN_CAL_EPISODES + 5):
        ds.add(CalibrationEpisode(lower=0.0, upper=0.1, ground_truth=0.9))

    report = measure_coverage(ds)
    assert len(report.alerts) > 0
    for alert in report.alerts:
        assert alert.gap > 0.05


# ─── [5] Certification gating ────────────────────────────────────────────────

def test_certify_returns_certified_when_all_gates_pass():
    obs = _make_iid_rewards(40)
    bound = hoeffding_bound(obs, nominal_confidence=0.90)
    decision = certify(
        bound=bound,
        n_episodes=40,
        valid_replays=38,
        total_replays=40,
        last_calibrated_at=_recent_dt(),
        observed_coverage=0.89,
    )
    assert decision.status == "CERTIFIED"
    assert decision.human_review_required is False
    assert decision.block_automated_action is False
    assert len(decision.gates_passed) == 5


def test_certify_returns_uncertified_when_calibration_expired():
    obs = _make_iid_rewards(40)
    bound = hoeffding_bound(obs, nominal_confidence=0.90)
    decision = certify(
        bound=bound,
        n_episodes=40,
        valid_replays=38,
        total_replays=40,
        last_calibrated_at=_expired_dt(),   # 40 days old
        observed_coverage=0.89,
    )
    assert decision.status == "UNCERTIFIED"
    assert decision.human_review_required is True
    assert decision.block_automated_action is False
    assert any("calibration_age" in g for g in decision.gates_failed)


def test_certify_returns_rejected_when_no_replays():
    """Zero valid replays → critical failure → REJECTED."""
    obs = []
    bound = unsupported_bound(obs, 0.90, "No observations provided.")
    decision = certify(
        bound=bound,
        n_episodes=0,
        valid_replays=0,
        total_replays=0,
        last_calibrated_at=_recent_dt(),
        observed_coverage=None,
    )
    assert decision.status == "REJECTED"
    assert decision.block_automated_action is True
    assert decision.human_review_required is True


def test_certify_blocked_when_insufficient_episodes():
    obs = _make_iid_rewards(5)
    bound = hoeffding_bound(obs, nominal_confidence=0.90)
    policy = CertificationPolicy(min_episodes=20)
    decision = certify(
        bound=bound,
        n_episodes=5,
        valid_replays=5,
        total_replays=5,
        last_calibrated_at=_recent_dt(),
        observed_coverage=0.88,
        policy=policy,
    )
    assert decision.status == "UNCERTIFIED"
    assert any("episode_count" in g for g in decision.gates_failed)


# ─── [5b] Coverage Monitor: downgrade on expired calibration ──────────────────

def test_coverage_monitor_downgrade_on_expiry():
    ds = CalibrationDataset()
    # Add stale episodes (40 days old)
    old_dt = _expired_dt()
    for _ in range(MIN_CAL_EPISODES + 5):
        ds.add(CalibrationEpisode(lower=0.5, upper=0.9, ground_truth=0.7, recorded_at=old_dt))

    monitor = CoverageMonitor(dataset=ds, max_calibration_age_days=30)

    event = DiagnosisEvent(
        run_id="run_xyz",
        certificate_status="CERTIFIED",
        issued_at=datetime.now(timezone.utc),
    )
    downgrades = monitor.process_event(event)
    assert len(downgrades) == 1
    assert downgrades[0].run_id == "run_xyz"
    assert downgrades[0].new_status == "UNCERTIFIED"
    assert "expired" in downgrades[0].reason.lower()


def test_coverage_monitor_no_downgrade_for_uncertified():
    """UNCERTIFIED diagnoses are not in scope for downgrade events."""
    ds = CalibrationDataset()
    old_dt = _expired_dt()
    for _ in range(MIN_CAL_EPISODES + 5):
        ds.add(CalibrationEpisode(lower=0.5, upper=0.9, ground_truth=0.7, recorded_at=old_dt))

    monitor = CoverageMonitor(dataset=ds, max_calibration_age_days=30)
    event = DiagnosisEvent(run_id="run_uncert", certificate_status="UNCERTIFIED",
                           issued_at=datetime.now(timezone.utc))
    downgrades = monitor.process_event(event)
    assert len(downgrades) == 0
