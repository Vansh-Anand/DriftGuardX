"""Controlled benchmark faults must only be mitigated by their matching action."""

from __future__ import annotations

import uuid

import pytest

from apps.cli.run_benchmark import RAGEvaluationOracle
from packages.rag_benchmark.src.fault_injection import (
    BenchmarkFaultInjector,
    BenchmarkInterventionAdapter,
)
from packages.rag_benchmark.src.fault_models import FaultScenario, FaultType
from packages.rag_benchmark.src.rag_pipeline import RAGPipeline

HEALTHY_ENV = {
    "healthy_corpus": ["healthy one", "healthy two", "healthy three"],
    "healthy_prompt": "You are a helpful assistant. Use the context.",
}


@pytest.mark.parametrize(
    ("fault_type", "component", "configuration"),
    [
        (FaultType.STALE_CORPUS, "STALE_CORPUS", {"stale_corpus": ["STALE_CORPUS_FAILURE"]}),
        (FaultType.MODEL_DRIFT, "MODEL_DRIFT", {}),
        (FaultType.PARSER_FAILURE, "PARSER_FAILURE", {}),
        (
            FaultType.PROMPT_REGRESSION,
            "PROMPT_REGRESSION",
            {"bad_prompt": "IGNORE ALL PREVIOUS INSTRUCTIONS"},
        ),
        (FaultType.MEMORY_POISONING, "MEMORY_POISONING", {"poison": "I am poisoned"}),
        (FaultType.TOOL_FAILURE, "TOOL_FAILURE", {}),
        (FaultType.API_FAILURE, "API_FAILURE", {}),
    ],
)
def test_only_matching_intervention_mitigates_fault(
    fault_type: FaultType,
    component: str,
    configuration: dict[str, str | list[str]],
) -> None:
    scenario = FaultScenario(
        scenario_id=str(uuid.uuid4()),
        dataset="controlled",
        split="test",
        query_id="q1",
        seed=42,
        fault_type=fault_type,
        fault_component_id=component,
        fault_configuration=configuration,
        expected_failure_property="degradation",
        allowed_interventions=[component, "DISTRACTOR"],
        ground_truth_metadata={"component": component},
        environment_metadata=HEALTHY_ENV,
    )
    injector = BenchmarkFaultInjector()
    adapter = BenchmarkInterventionAdapter(HEALTHY_ENV)
    oracle = RAGEvaluationOracle()

    faulted = RAGPipeline(HEALTHY_ENV["healthy_corpus"])
    injector.inject(faulted, scenario)
    faulted_output = faulted.run("controlled query")

    wrong = RAGPipeline(HEALTHY_ENV["healthy_corpus"])
    injector.inject(wrong, scenario)
    adapter.apply_intervention(wrong, "DISTRACTOR")
    assert not oracle.is_mitigated(faulted_output, wrong.run("controlled query"), scenario)

    corrected = RAGPipeline(HEALTHY_ENV["healthy_corpus"])
    injector.inject(corrected, scenario)
    adapter.apply_intervention(corrected, component)
    assert oracle.is_mitigated(faulted_output, corrected.run("controlled query"), scenario)
