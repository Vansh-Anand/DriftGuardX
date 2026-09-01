"""
DriftGuard-X v2 — Detector Calibration Pipeline
"""

from collections.abc import Sequence

import numpy as np


def calculate_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    """Calculate TN, FP, FN, TP."""
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    tp = np.sum((y_true == 1) & (y_pred == 1))
    return int(tn), int(fp), int(fn), int(tp)


def calculate_metrics_for_threshold(
    y_true: Sequence[int], y_score: Sequence[float], threshold: float
) -> dict[str, float]:
    """Calculate F1, FPR, TPR for a specific threshold."""
    y_true_np = np.array(y_true)
    y_pred = (np.array(y_score) >= threshold).astype(int)

    tn, fp, fn, tp = calculate_confusion_matrix(y_true_np, y_pred)

    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tpr

    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "tpr": float(tpr),
        "fpr": float(fpr),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def compute_auroc_auprc(y_true: Sequence[int], y_score: Sequence[float]) -> tuple[float, float]:
    """Compute AUROC and average precision without a sklearn dependency.

    The precision-recall curve is traversed in descending score order.  The
    previous implementation reversed both axes before integration, which made
    recall decrease and produced impossible negative AUPRC values.
    """
    if len(y_true) != len(y_score):
        raise ValueError("y_true and y_score must have the same length")
    if not y_true:
        raise ValueError("at least one observation is required")

    y_true_np = np.asarray(y_true, dtype=int)
    y_score_np = np.asarray(y_score, dtype=float)
    if not np.isin(y_true_np, (0, 1)).all():
        raise ValueError("y_true must contain only binary labels 0 and 1")
    if not np.isfinite(y_score_np).all():
        raise ValueError("y_score must contain only finite values")

    if len(np.unique(y_true_np)) < 2:
        return 0.0, 0.0

    thresholds = np.unique(y_score_np)
    thresholds = np.sort(thresholds)[::-1]  # descending

    tprs, fprs = [0.0], [0.0]

    for t in thresholds:
        m = calculate_metrics_for_threshold(y_true, y_score, t)
        tprs.append(m["tpr"])
        fprs.append(m["fpr"])

    tprs.append(1.0)
    fprs.append(1.0)

    # AUROC uses trapezoidal integration along monotonically increasing FPR.
    auroc = np.trapezoid(tprs, fprs)

    # Average precision is the accepted step-wise area summary for a ranked
    # precision-recall curve and is stable in the presence of tied scores.
    order = np.argsort(-y_score_np, kind="stable")
    sorted_truth = y_true_np[order]
    true_positives = np.cumsum(sorted_truth)
    ranks = np.arange(1, len(sorted_truth) + 1)
    precision_at_rank = true_positives / ranks
    positive_count = int(np.sum(sorted_truth))
    auprc = float(np.sum(precision_at_rank * sorted_truth) / positive_count)

    return float(np.clip(auroc, 0.0, 1.0)), float(np.clip(auprc, 0.0, 1.0))


def calibrate_detector(
    y_true: Sequence[int], y_score: Sequence[float], target_fpr: float = 0.05
) -> dict[str, float]:
    """
    Find optimal threshold that maintains FPR <= target_fpr while maximizing F1.
    """
    y_score_np = np.array(y_score)
    thresholds = np.unique(y_score_np)

    best_threshold = float(thresholds[0])
    best_f1 = -1.0
    best_metrics = {}

    for t in thresholds:
        m = calculate_metrics_for_threshold(y_true, y_score, t)
        if m["fpr"] <= target_fpr and m["f1"] >= best_f1:
            best_f1 = m["f1"]
            best_threshold = float(t)
            best_metrics = m

    auroc, auprc = compute_auroc_auprc(y_true, y_score)

    return {
        "optimal_threshold": best_threshold,
        "f1": best_metrics.get("f1", 0.0),
        "fpr": best_metrics.get("fpr", 0.0),
        "tpr": best_metrics.get("tpr", 0.0),
        "auroc": auroc,
        "auprc": auprc,
    }
