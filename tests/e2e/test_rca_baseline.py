from uuid import UUID

from packages.contracts.src.models import ComponentType
from packages.evaluation.src.benchmark import ExhaustiveBenchmarkRunner
from packages.evaluation.src.contribution import calculate_contribution_vector
from packages.evaluation.src.rca_metrics import RCAMetricsEvaluator


def test_contribution_vector():
    vec = calculate_contribution_vector(
        reliability_improvements=[0.1, 0.15, 0.12],
        cost_delta_usd=0.01,
        latency_delta_ms=50.0,
        risk_penalty=0.0,
        invalid_count=0,
        total_trials=3,
    )

    assert vec.reliability_improvement_mean > 0.1
    assert vec.aggregate_score > 0.0
    assert vec.invalid_rate == 0.0


def test_benchmark_negative_controls():
    runner = ExhaustiveBenchmarkRunner(trials_per_candidate=3)
    results = runner.execute_matched_set(UUID(int=1), ComponentType.RETRIEVER)

    assert "optimal_intervention" in results
    assert "negative_control_noop" in results

    noop_score = results["negative_control_noop"].aggregate_score
    optimal_score = results["optimal_intervention"].aggregate_score

    # Negative control should perform materially worse
    assert noop_score < optimal_score

    # Abstention logic check
    should_abstain = RCAMetricsEvaluator.check_abstention(noop_score, threshold=0.05)
    assert should_abstain is True


def test_rca_metrics_multi_fault():
    # True faults are Retriever and Generator
    ground_truth = {"retriever_v1", "generator_v2"}

    # Model predicted Retriever as rank 1, but missed Generator in top 2
    predicted = ["retriever_v1", "policy_v3", "generator_v2"]

    p1 = RCAMetricsEvaluator.calculate_precision_at_k(predicted, ground_truth, 1)
    p3 = RCAMetricsEvaluator.calculate_precision_at_k(predicted, ground_truth, 3)
    mrr = RCAMetricsEvaluator.calculate_mrr(predicted, ground_truth)

    assert p1 == 0.5  # 1 hit out of 2 true faults in top 1
    assert p3 == 1.0  # 2 hits out of 2 true faults in top 3
    assert mrr == 1.0  # First hit is at rank 1
