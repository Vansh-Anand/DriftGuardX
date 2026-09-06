"""
DriftGuard-X v2 — Benchmark Causal Fault Models
"""

import abc
import enum
import hashlib
from typing import Any

from pydantic import Field

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.models import DGXBaseModel


class FaultType(str, enum.Enum):
    STALE_CORPUS = "STALE_CORPUS"
    MODEL_DRIFT = "MODEL_DRIFT"
    PARSER_FAILURE = "PARSER_FAILURE"
    PROMPT_REGRESSION = "PROMPT_REGRESSION"
    MEMORY_POISONING = "MEMORY_POISONING"
    TOOL_FAILURE = "TOOL_FAILURE"
    API_FAILURE = "API_FAILURE"
    CONTEXT_TRUNCATION = "CONTEXT_TRUNCATION"
    EMBEDDING_DRIFT = "EMBEDDING_DRIFT"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    LLM_DEGRADATION = "LLM_DEGRADATION"
    MALFORMED_TOOL_OUTPUT = "MALFORMED_TOOL_OUTPUT"
    STALE_MEMORY = "STALE_MEMORY"
    POLICY_FAILURE = "POLICY_FAILURE"
    ROUTING_FAILURE = "ROUTING_FAILURE"
    MULTI_AGENT_CASCADING_FAILURE = "MULTI_AGENT_CASCADING_FAILURE"
    HALLUCINATED_CITATION = "HALLUCINATED_CITATION"
    COMPOUND = "COMPOUND"


class FaultScenario(DGXBaseModel):
    """Configuration for a specific benchmark trial scenario."""

    scenario_id: str
    dataset: str
    split: str
    query_id: str
    seed: int
    fault_type: FaultType
    fault_component_id: str
    fault_configuration: dict[str, Any]
    expected_failure_property: str
    allowed_interventions: list[str]
    ground_truth_metadata: dict[str, Any]
    environment_metadata: dict[str, Any]


class FaultInjector(abc.ABC):
    """Injects a fault into a pipeline instance."""

    @abc.abstractmethod
    def inject(self, pipeline: Any, scenario: FaultScenario) -> None:
        pass


class SyntheticFaultInjector(FaultInjector):
    """Injects faults by monkey-patching Python objects (mock/synthetic)."""

    pass


class RealControlledFaultInjector(FaultInjector):
    """Injects genuine infrastructural faults (e.g., SQL corruption, network config)."""

    pass


class InterventionAdapter(abc.ABC):
    """Applies a proposed recovery intervention to the pipeline instance."""

    @abc.abstractmethod
    def apply_intervention(self, pipeline: Any, target_component_id: str) -> None:
        """Applies a fix to the target_component_id if valid."""
        pass


class EvaluationOracle(abc.ABC):
    """Evaluates the pipeline outcome to determine if the failure was mitigated."""

    @abc.abstractmethod
    def is_mitigated(
        self, original_faulted_output: Any, new_output: Any, scenario: FaultScenario
    ) -> bool:
        pass


class BenchmarkTrial(DGXBaseModel):
    """Records the execution of a single benchmark trial."""

    scenario: FaultScenario
    strategy: str
    replays_executed: int
    cost_usd: float
    blast_radius: float
    posterior_max: float
    cut_size: int
    correct: bool
    stop_reason: str
    wall_seconds: float
    unresolved: bool
    false_confirmed: bool
    confirmed: bool = False
    mitigation_observed: bool = False
    localization_correct: bool = False
    top_candidate: str | None = None
    observations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_kind: EvidenceClassification = EvidenceClassification.SYNTHETIC_SIMULATION


def generate_stable_seed(
    dataset: str, split: str, query_id: str, fault_type: str, replicate_id: int, global_seed: int
) -> int:
    """Derives a deterministic trial seed."""
    key = f"{dataset}|{split}|{query_id}|{fault_type}|{replicate_id}|{global_seed}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:15], 16)
