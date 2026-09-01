import math

import pytest

from packages.detectors.src.calibration import compute_auroc_auprc


def test_perfect_ranking_has_unit_auroc_and_auprc() -> None:
    auroc, auprc = compute_auroc_auprc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])

    assert auroc == pytest.approx(1.0)
    assert auprc == pytest.approx(1.0)


def test_reversed_ranking_metrics_are_bounded() -> None:
    auroc, auprc = compute_auroc_auprc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9])

    assert auroc == pytest.approx(0.0)
    assert auprc == pytest.approx((1 / 3 + 2 / 4) / 2)
    assert 0.0 <= auprc <= 1.0


@pytest.mark.parametrize(
    ("truth", "scores"),
    [
        ([0, 1], [0.5]),
        ([], []),
        ([0, 2], [0.1, 0.2]),
        ([0, 1], [0.1, math.inf]),
    ],
)
def test_invalid_calibration_inputs_fail_closed(truth: list[int], scores: list[float]) -> None:
    with pytest.raises(ValueError):
        compute_auroc_auprc(truth, scores)
