import pytest

from packages.bcrb.src.calibration import BCRBCalibrator


def test_estimate_reliability_delta():
    calibrator = BCRBCalibrator()
    # Generator should have base 0.7
    delta = calibrator.estimate_reliability_delta("generator", "restart")
    assert delta == 0.7

    # Retriever should have base 0.8
    delta = calibrator.estimate_reliability_delta("retriever", "restart")
    assert delta == 0.8

    # Rollback should add 0.1
    delta = calibrator.estimate_reliability_delta("retriever", "rollback")
    assert delta == 0.9  # 0.8 + 0.1

    # Fallback default
    delta = calibrator.estimate_reliability_delta("unknown", "restart")
    assert delta == 0.5


def test_compute_brier_score():
    calibrator = BCRBCalibrator()
    preds = [0.8, 0.2, 0.9, 0.1]
    obs = [1, 0, 1, 0]

    score = calibrator.compute_brier_score(preds, obs)
    # (0.2^2 + 0.2^2 + 0.1^2 + 0.1^2) / 4 = (0.04 + 0.04 + 0.01 + 0.01) / 4 = 0.1 / 4 = 0.025
    assert score == pytest.approx(0.025)


def test_compute_expected_calibration_error():
    calibrator = BCRBCalibrator()
    # All predictions in one bin [0.8, 0.9)
    # Average pred = 0.85
    # Average obs = 1.0
    # ECE = |0.85 - 1.0| = 0.15
    preds = [0.8, 0.9]
    obs = [1, 1]

    ece = calibrator.compute_expected_calibration_error(preds, obs, bins=2)
    # Bin boundaries: [0, 0.5, 1.0]
    # Both preds are in bin [0.5, 1.0]
    # Avg pred = 0.85, avg obs = 1.0
    # ECE = 1.0 * |0.85 - 1.0| = 0.15
    assert ece == pytest.approx(0.15)


def test_generate_calibration_curve():
    calibrator = BCRBCalibrator()
    preds = [0.1, 0.2, 0.8, 0.9]
    obs = [0, 0, 1, 1]

    mean_preds, frac_pos = calibrator.generate_calibration_curve(preds, obs, bins=2)
    # Bin boundaries: [0, 0.5, 1.0]
    # Bin 1 (0-0.5): preds [0.1, 0.2], obs [0, 0]
    # Bin 2 (0.5-1.0): preds [0.8, 0.9], obs [1, 1]
    assert len(mean_preds) == 2
    assert len(frac_pos) == 2

    assert mean_preds[0] == pytest.approx(0.15)
    assert frac_pos[0] == pytest.approx(0.0)

    assert mean_preds[1] == pytest.approx(0.85)
    assert frac_pos[1] == pytest.approx(1.0)
