
import numpy as np
from scipy import stats


def compute_confidence_intervals(data: list[float], confidence: float = 0.95) -> tuple[float, float]:
    if len(data) == 0:
        return 0.0, 0.0
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    if se == 0:
        return m, m
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return m - h, m + h

def failure_subset_analysis(raw_predictions: list[dict]) -> dict[str, int]:
    """Identifies intersections and breakdown of failures."""
    breakdown = {"retriever": 0, "generator": 0, "tool": 0}
    for pred in raw_predictions:
        if pred["status"] == "FAILURE":
            # Mock assigning blame to components based on metrics (in reality RCA provides this)
            if "relevance" in pred.get("metrics", {}) and pred["metrics"]["relevance"] < 0.5:
                breakdown["retriever"] += 1
            elif "tool_accuracy" in pred.get("metrics", {}) and pred["metrics"]["tool_accuracy"] < 0.5:
                breakdown["tool"] += 1
            else:
                breakdown["generator"] += 1
    return breakdown

def paired_bootstrap_interval(data_a: list[float], data_b: list[float], n_bootstraps: int = 10000, alpha: float = 0.05) -> tuple[float, float]:
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

def permutation_test(data_a: list[float], data_b: list[float], n_permutations: int = 10000) -> float:
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
