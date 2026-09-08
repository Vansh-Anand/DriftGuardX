"""Regression checks for numeric evidence and finite-sample conformal ranks."""

import math
from datetime import UTC, datetime

import pytest

from packages.evaluation.src.bounds import bootstrap_bound, conformal_bound, hoeffding_bound
from packages.evaluation.src.certification import certify


@pytest.mark.parametrize("confidence", [0, 1, -0.1, 1.1, math.nan, math.inf])
@pytest.mark.parametrize("method", [hoeffding_bound, bootstrap_bound, conformal_bound])
def test_invalid_confidence_fails_closed(method, confidence):
    kwargs = {"new_score": 0.5} if method is conformal_bound else {}
    result = method([0.2] * 20, nominal_confidence=confidence, **kwargs)
    assert not result.is_supported
    assert result.lower is None and result.upper is None


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("method", [hoeffding_bound, bootstrap_bound, conformal_bound])
def test_nonfinite_observations_cannot_certify(method, invalid):
    kwargs = {"new_score": 0.5} if method is conformal_bound else {}
    bound = method([0.2] * 19 + [invalid], **kwargs)
    assert not bound.is_supported
    decision = certify(
        bound=bound,
        n_episodes=20,
        valid_replays=20,
        total_replays=20,
        last_calibrated_at=datetime.now(UTC),
        observed_coverage=0.99,
    )
    assert decision.status == "REJECTED"
    assert decision.block_automated_action


@pytest.mark.parametrize("count", [0, -1, True, 2.5])
def test_invalid_bootstrap_count_fails_closed(count):
    assert not bootstrap_bound([0.2] * 20, n_resamples=count).is_supported


def test_conformal_uses_one_based_order_statistic():
    result = conformal_bound(list(range(1, 21)), new_score=100, nominal_confidence=0.9)
    assert result.epsilon == 19
    assert (result.lower, result.upper) == (81, 119)


def test_conformal_cannot_clamp_an_unattainable_rank():
    result = conformal_bound([0.1] * 10, new_score=0, nominal_confidence=0.99)
    assert not result.is_supported
    assert result.lower is None and result.upper is None


def test_conformal_rejects_negative_residual_and_nonfinite_center():
    assert not conformal_bound([-0.1] * 20, new_score=0).is_supported
    assert not conformal_bound([0.1] * 20, new_score=math.inf).is_supported


def test_conformal_rank_coverage_on_all_exchangeable_holdouts():
    # Each of these 21 distinct residuals is equally likely to be the held-out one.
    scores = list(range(1, 22))
    covered = 0
    for held_out in scores:
        bound = conformal_bound([s for s in scores if s != held_out], new_score=0)
        covered += held_out <= bound.upper
    assert covered == 19
    assert covered / len(scores) >= 0.9


def test_hoeffding_range_and_scaling():
    assert not hoeffding_bound([0.5], reward_max=math.inf).is_supported
    assert not hoeffding_bound([1 + 1e-10]).is_supported
    result = hoeffding_bound([2.0] * 40, reward_min=1, reward_max=3)
    assert result.epsilon == pytest.approx(2 * math.sqrt(math.log(20) / 80))
