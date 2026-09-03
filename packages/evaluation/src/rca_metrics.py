"""
DriftGuard-X v2 — RCA Metrics
PRIVATE — All Rights Reserved.
"""


class RCAMetricsEvaluator:
    """
    Evaluates the performance of the Root Cause Analysis engine
    against ground-truth injected faults.
    """

    @staticmethod
    def calculate_precision_at_k(
        predicted_ranked: list[str], ground_truth: set[str], k: int
    ) -> float:
        """
        Partial-credit precision@k for multi-fault scenarios.
        E.g. if 2 faults exist, finding 1 in top-k gives 0.5 points.
        """
        if not ground_truth:
            return 1.0 if not predicted_ranked else 0.0

        top_k = predicted_ranked[:k]
        hits = sum(1 for p in top_k if p in ground_truth)

        # We cap at the number of ground truth faults to avoid > 1.0
        return hits / len(ground_truth)

    @staticmethod
    def calculate_mrr(predicted_ranked: list[str], ground_truth: set[str]) -> float:
        """
        Mean Reciprocal Rank. For multi-fault, we use the rank of the *first* hit.
        """
        if not ground_truth:
            return 1.0 if not predicted_ranked else 0.0

        for i, p in enumerate(predicted_ranked):
            if p in ground_truth:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def check_abstention(best_reliability_improvement: float, threshold: float = 0.05) -> bool:
        """
        Abstention check: returns True if no candidate provides material improvement.
        """
        return best_reliability_improvement < threshold
