"""
DriftGuard-X v2 — Statistical Baselines for Drift Detectors
"""
import numpy as np
from scipy import stats
from typing import Sequence, Tuple


def check_threshold(value: float, threshold: float, operator: str) -> bool:
    """Returns True if the value breaches the threshold (i.e. is an anomaly)."""
    if operator == ">":
        return value > threshold
    elif operator == "<":
        return value < threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == "==":
        return value == threshold
    elif operator == "!=":
        return value != threshold
    raise ValueError(f"Unknown operator: {operator}")


def compute_ewma(series: Sequence[float], alpha: float = 0.3) -> list[float]:
    """Compute Exponentially Weighted Moving Average."""
    if not series:
        return []
    ewma = [series[0]]
    for x in series[1:]:
        ewma.append(alpha * x + (1 - alpha) * ewma[-1])
    return ewma


def compute_z_score(value: float, reference_series: Sequence[float]) -> float:
    """Compute standard z-score against a reference distribution."""
    if not reference_series or len(reference_series) < 2:
        return 0.0
    mean = np.mean(reference_series)
    std = np.std(reference_series)
    if std == 0:
        return 0.0
    return float((value - mean) / std)


def compute_psi(expected: Sequence[float], actual: Sequence[float], bins: int = 10) -> float:
    """Compute Population Stability Index (PSI) between two distributions."""
    if not expected or not actual:
        return 0.0
    
    # Define bins based on expected
    min_val = min(min(expected), min(actual))
    max_val = max(max(expected), max(actual))
    
    if min_val == max_val:
        return 0.0
        
    bins_edges = np.linspace(min_val, max_val, bins + 1)
    
    # Calculate counts
    expected_counts, _ = np.histogram(expected, bins=bins_edges)
    actual_counts, _ = np.histogram(actual, bins=bins_edges)
    
    # Convert to fractions and add small epsilon to avoid div by zero
    expected_fracs = (expected_counts + 1e-4) / (sum(expected_counts) + 1e-4 * bins)
    actual_fracs = (actual_counts + 1e-4) / (sum(actual_counts) + 1e-4 * bins)
    
    # Calculate PSI
    psi_values = (actual_fracs - expected_fracs) * np.log(actual_fracs / expected_fracs)
    return float(np.sum(psi_values))


def ks_test(expected: Sequence[float], actual: Sequence[float]) -> Tuple[float, float]:
    """
    Perform Kolmogorov-Smirnov test.
    Returns (statistic, p_value).
    """
    if not expected or not actual:
        return 0.0, 1.0
    stat, p_value = stats.ks_2samp(expected, actual)
    return float(stat), float(p_value)


def jensen_shannon_divergence(p: Sequence[float], q: Sequence[float], bins: int = 10) -> float:
    """Compute Jensen-Shannon Divergence between two empirical distributions."""
    if not p or not q:
        return 0.0
        
    min_val = min(min(p), min(q))
    max_val = max(max(p), max(q))
    
    if min_val == max_val:
        return 0.0
        
    bins_edges = np.linspace(min_val, max_val, bins + 1)
    p_counts, _ = np.histogram(p, bins=bins_edges, density=True)
    q_counts, _ = np.histogram(q, bins=bins_edges, density=True)
    
    p_counts = p_counts + 1e-10
    q_counts = q_counts + 1e-10
    p_counts /= p_counts.sum()
    q_counts /= q_counts.sum()
    
    m = 0.5 * (p_counts + q_counts)
    
    # Compute Kullback-Leibler divergences
    kl_pm = stats.entropy(p_counts, m)
    kl_qm = stats.entropy(q_counts, m)
    
    jsd = 0.5 * (kl_pm + kl_qm)
    return float(jsd)


def cusum_change_point(series: Sequence[float], threshold: float = 5.0, drift: float = 0.0) -> bool:
    """
    Cumulative Sum (CUSUM) simple change-point detection.
    Returns True if a change point is detected.
    """
    if not series:
        return False
        
    mean = np.mean(series)
    pos_sum = 0.0
    neg_sum = 0.0
    
    for x in series:
        s_pos = x - mean - drift
        s_neg = mean - x - drift
        
        pos_sum = max(0.0, pos_sum + s_pos)
        neg_sum = max(0.0, neg_sum + s_neg)
        
        if pos_sum > threshold or neg_sum > threshold:
            return True
            
    return False
