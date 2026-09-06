import os
from unittest.mock import MagicMock

from packages.rag_benchmark.src.fault_models import FaultScenario, FaultType
from packages.rag_benchmark.src.real_fault_injector import GenuineFaultInjector


class MockRetriever:
    embedding_dim = 768


class MockPipeline:
    def __init__(self):
        self.retriever = MockRetriever()
        self.prompt_template = "original_prompt"
        self.llm = MagicMock()


def test_genuine_fault_injector_embedding_mismatch():
    pipeline = MockPipeline()
    injector = GenuineFaultInjector()

    scenario = FaultScenario(
        scenario_id="1",
        dataset="test",
        split="test",
        query_id="q1",
        seed=42,
        fault_type=FaultType.EMBEDDING_DRIFT,
        fault_component_id="retriever",
        fault_configuration={},
        expected_failure_property="error",
        allowed_interventions=[],
        ground_truth_metadata={},
        environment_metadata={},
    )

    injector.inject(pipeline, scenario)
    assert pipeline.retriever.embedding_dim == 1536
    assert os.environ["EMBEDDING_DIM"] == "1536"

    injector.reset(pipeline)
    assert pipeline.retriever.embedding_dim == 768
    # Depending on original env it might be popped or restored, if missing it pops


def test_genuine_fault_injector_prompt_regression():
    pipeline = MockPipeline()
    injector = GenuineFaultInjector()

    scenario = FaultScenario(
        scenario_id="2",
        dataset="test",
        split="test",
        query_id="q2",
        seed=42,
        fault_type=FaultType.PROMPT_REGRESSION,
        fault_component_id="prompt",
        fault_configuration={},
        expected_failure_property="error",
        allowed_interventions=[],
        ground_truth_metadata={},
        environment_metadata={},
    )

    injector.inject(pipeline, scenario)
    assert pipeline.prompt_template == "Context: {query}\nProvide a single word answer: ERROR."

    injector.reset(pipeline)
    assert pipeline.prompt_template == "original_prompt"


def test_genuine_fault_injector_sql_tombstone():
    db_mock = MagicMock()
    injector = GenuineFaultInjector(db_session=db_mock)
    pipeline = MockPipeline()

    scenario = FaultScenario(
        scenario_id="3",
        dataset="test",
        split="test",
        query_id="q3",
        seed=42,
        fault_type=FaultType.RETRIEVAL_FAILURE,
        fault_component_id="retriever",
        fault_configuration={},
        expected_failure_property="error",
        allowed_interventions=[],
        ground_truth_metadata={},
        environment_metadata={},
    )

    injector.inject(pipeline, scenario)
    db_mock.execute.assert_called_with(
        "UPDATE document_chunks SET is_deleted = True WHERE id IN (SELECT id FROM document_chunks ORDER BY RANDOM() LIMIT 5)"
    )
    db_mock.commit.assert_called()
