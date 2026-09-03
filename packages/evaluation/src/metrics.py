"""
DriftGuard-X v2 — Reliability Metrics
PRIVATE — All Rights Reserved.
"""

from pydantic import BaseModel, Field


class ReliabilityVector(BaseModel):
    """
    Standardized vector capturing multi-dimensional reliability of an episode.
    """

    faithfulness: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    task_success: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_consistency: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_validity: float = Field(default=0.0, ge=0.0, le=1.0)
    memory_safety: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_compliance: float = Field(default=1.0, ge=0.0, le=1.0)  # 1.0 = compliant

    latency_ms: float = Field(default=0.0, ge=0.0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    operational_errors: int = Field(default=0, ge=0)

    # Store evaluator settings for transparency
    evaluator_versions: dict[str, str] = Field(default_factory=dict)
    confidence_labels: dict[str, str] = Field(default_factory=dict)


import numpy as np


class DeterministicMetricsEngine:
    @staticmethod
    def calculate_recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        if not relevant_ids:
            return 1.0
        retrieved_k = retrieved_ids[:k]
        hits = sum(1 for rid in relevant_ids if rid in retrieved_k)
        return hits / len(relevant_ids)

    @staticmethod
    def calculate_precision_at_k(
        retrieved_ids: list[str], relevant_ids: list[str], k: int
    ) -> float:
        retrieved_k = retrieved_ids[:k]
        if not retrieved_k:
            return 0.0
        hits = sum(1 for rid in retrieved_k if rid in relevant_ids)
        return hits / len(retrieved_k)

    @staticmethod
    def calculate_mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        for i, rid in enumerate(retrieved_ids):
            if rid in relevant_ids:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def calculate_ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        retrieved_k = retrieved_ids[:k]
        dcg = sum(1.0 / np.log2(i + 2) for i, rid in enumerate(retrieved_k) if rid in relevant_ids)
        idcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant_ids), k)))
        if idcg == 0.0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def calculate_rca_metrics(predictions: list[str], ground_truths: list[str]) -> dict[str, float]:
        # Binary comparison if single prediction
        if not predictions or not ground_truths:
            return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        # Exact match for top-1
        top_1_acc = 1.0 if predictions[0] == ground_truths[0] else 0.0

        # Set based precision/recall for all
        pred_set = set(predictions)
        gt_set = set(ground_truths)
        tp = len(pred_set.intersection(gt_set))
        fp = len(pred_set - gt_set)
        fn = len(gt_set - pred_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {"accuracy": top_1_acc, "precision": precision, "recall": recall, "f1": f1}

    @staticmethod
    def calculate_confidence_intervals(
        metrics: list[float], confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculates the standard error margin (95% CI by default) for a list of metrics."""
        import scipy.stats as stats

        if not metrics or len(metrics) < 2:
            return 0.0, 0.0

        a = 1.0 * np.array(metrics)
        m, se = np.mean(a), stats.sem(a)
        h = se * stats.t.ppf((1 + confidence) / 2.0, len(a) - 1)
        return float(m - h), float(m + h)
