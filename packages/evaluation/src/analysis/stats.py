import numpy as np
from scipy import stats


def compute_confidence_intervals(
    data: list[float], confidence: float = 0.95
) -> tuple[float, float]:
    if len(data) == 0:
        return 0.0, 0.0
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    if se == 0:
        return m, m
    h = se * stats.t.ppf((1 + confidence) / 2.0, n - 1)
    return m - h, m + h


def failure_subset_analysis(raw_predictions: list[dict]) -> dict[str, int]:
    """Identifies intersections and breakdown of failures."""
    breakdown = {"retriever": 0, "generator": 0, "tool": 0}
    for pred in raw_predictions:
        if pred["status"] == "FAILURE":
            # Mock assigning blame to components based on metrics (in reality RCA provides this)
            if "relevance" in pred.get("metrics", {}) and pred["metrics"]["relevance"] < 0.5:
                breakdown["retriever"] += 1
            elif (
                "tool_accuracy" in pred.get("metrics", {})
                and pred["metrics"]["tool_accuracy"] < 0.5
            ):
                breakdown["tool"] += 1
            else:
                breakdown["generator"] += 1
    return breakdown


def paired_bootstrap_interval(
    data_a: list[float], data_b: list[float], n_bootstraps: int = 10000, alpha: float = 0.05
) -> tuple[float, float]:
    """Computes a paired bootstrap confidence interval for the mean difference (A - B)."""
    assert len(data_a) == len(data_b), "Data must be paired"
    diffs = np.array(data_a) - np.array(data_b)
    boot_means = []
    n = len(diffs)
    for _ in range(n_bootstraps):
        sample = np.random.choice(diffs, size=n, replace=True)
        boot_means.append(np.mean(sample))
    lower = np.percentile(boot_means, 100 * (alpha / 2))
    upper = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return float(lower), float(upper)


def permutation_test(
    data_a: list[float], data_b: list[float], n_permutations: int = 10000
) -> float:
    """Performs a paired permutation test and returns the p-value."""
    assert len(data_a) == len(data_b), "Data must be paired"
    diffs = np.array(data_a) - np.array(data_b)
    observed_mean = np.abs(np.mean(diffs))

    count = 0
    n = len(diffs)
    for _ in range(n_permutations):
        signs = np.random.choice([-1, 1], size=n)
        perm_mean = np.abs(np.mean(diffs * signs))
        if perm_mean >= observed_mean:
            count += 1

    return float(count / n_permutations)


def cohens_d(data_a: list[float], data_b: list[float]) -> float:
    """Computes Cohen's d effect size for paired samples (using the standard deviation of differences)."""
    diffs = np.array(data_a) - np.array(data_b)
    mean_diff = np.mean(diffs)
    std_diff = np.std(diffs, ddof=1)
    if std_diff == 0:
        return 0.0
    return float(mean_diff / std_diff)


def bonferroni_correction(p_values: list[float]) -> list[float]:
    """Applies Bonferroni correction to a list of p-values."""
    m = len(p_values)
    return [min(1.0, p * m) for p in p_values]


def compute_comprehensive_stats(
    baseline_data: list[float], proposed_data: list[float], alpha: float = 0.05
) -> dict:
    """Computes a comprehensive set of statistics comparing a proposed approach to a baseline.

    Args:
        baseline_data: Metric values for the baseline approach across N trials/seeds.
        proposed_data: Metric values for the proposed approach across N trials/seeds.
        alpha: Significance level.

    Returns:
        A dictionary containing:
        - N: Number of paired observations
        - baseline_mean: Mean of the baseline
        - baseline_median: Median of the baseline
        - baseline_std: Standard deviation of the baseline
        - proposed_mean: Mean of the proposed approach
        - proposed_median: Median of the proposed approach
        - proposed_std: Standard deviation of the proposed approach
        - 95_ci_lower: Lower bound of the paired 95% CI for (Proposed - Baseline)
        - 95_ci_upper: Upper bound of the paired 95% CI for (Proposed - Baseline)
        - effect_size_cohens_d: Cohen's d
        - p_value: Paired permutation test p-value
    """
    n = len(baseline_data)
    assert n == len(proposed_data), "Data arrays must be of equal length for paired tests"

    if n == 0:
        return {}

    b_arr = np.array(baseline_data)
    p_arr = np.array(proposed_data)

    lower_ci, upper_ci = paired_bootstrap_interval(proposed_data, baseline_data, alpha=alpha)
    p_val = permutation_test(proposed_data, baseline_data)
    effect_size = cohens_d(proposed_data, baseline_data)

    return {
        "N": n,
        "baseline_mean": float(np.mean(b_arr)),
        "baseline_median": float(np.median(b_arr)),
        "baseline_std": float(np.std(b_arr, ddof=1) if n > 1 else 0.0),
        "proposed_mean": float(np.mean(p_arr)),
        "proposed_median": float(np.median(p_arr)),
        "proposed_std": float(np.std(p_arr, ddof=1) if n > 1 else 0.0),
        "mean_diff": float(np.mean(p_arr - b_arr)),
        "95_ci_lower": lower_ci,
        "95_ci_upper": upper_ci,
        "effect_size_cohens_d": effect_size,
        "p_value": p_val,
    }
