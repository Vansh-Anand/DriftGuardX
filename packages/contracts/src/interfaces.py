"""
DriftGuard-X v2 — Orchestration Interfaces
PRIVATE — All Rights Reserved.
"""
import abc
from typing import Any

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    RecoveryValidationResult,
    ReplayEquivalenceEnvelope,
    SignedCapability,
)
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
)


class DivergenceReport:
    """
    Structured result of divergence validation — not a bare bool.
    Returned by DivergenceValidator.validate_divergence().
    """
    def __init__(
        self,
        valid: bool,
        reason: str = "",
        per_node: dict[str, Any] | None = None,
        early_terminated: bool = False,
        violated_frozen_nodes: list[str] | None = None,
        violated_forbidden_nodes: list[str] | None = None,
    ) -> None:
        self.valid = valid
        self.reason = reason
        self.per_node: dict[str, Any] = per_node or {}
        self.early_terminated = early_terminated
        self.violated_frozen_nodes: list[str] = violated_frozen_nodes or []
        self.violated_forbidden_nodes: list[str] = violated_forbidden_nodes or []

    def __bool__(self) -> bool:
        return self.valid


class ResourceContext:
    """Tracks resource consumption during the experiment loop."""
    def __init__(self, budget_usd: float = 10.0, max_wall_seconds: float = 300.0) -> None:
        self.budget_usd = budget_usd
        self.max_wall_seconds = max_wall_seconds
        self.spent_usd: float = 0.0
        self.elapsed_seconds: float = 0.0
        self.replay_count: int = 0

    def reserve(self, cost_usd: float) -> bool:
        """Returns True if reservation succeeds, False if budget exceeded."""
        if self.spent_usd + cost_usd > self.budget_usd:
            return False
        self.spent_usd += cost_usd
        self.replay_count += 1
        return True

    def budget_exhausted(self) -> bool:
        return self.spent_usd >= self.budget_usd or self.elapsed_seconds >= self.max_wall_seconds


class TraceProvider(abc.ABC):
    @abc.abstractmethod
    def get_trace(self, incident_id: str) -> dict[str, Any]:
        pass


class GraphProvider(abc.ABC):
    @abc.abstractmethod
    def get_causal_graph(self, incident_id: str) -> dict[str, Any]:
        pass


class InterventionGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_candidates(self, incident_state: IncidentState) -> list[dict[str, Any]]:
        pass


class EnvelopeBuilder(abc.ABC):
    @abc.abstractmethod
    def build_envelope(
        self, incident_id: str, candidates: list[dict[str, Any]]
    ) -> ReplayEquivalenceEnvelope:
        pass


class RAEBGateway(abc.ABC):
    @abc.abstractmethod
    def check_admissibility(self, envelope: ReplayEquivalenceEnvelope) -> bool:
        pass


class ExogenousStateController(abc.ABC):
    """
    Controls all non-deterministic external state during replay.
    Intercepts: RNG, time, API responses, DB snapshots, LLMs, tools, feature flags.
    """
    @abc.abstractmethod
    def __enter__(self) -> "ExogenousStateController":
        pass

    @abc.abstractmethod
    def __exit__(self, *args: Any) -> None:
        pass


class ExperimentPlanner(abc.ABC):
    @abc.abstractmethod
    def plan_next_experiment(
        self,
        envelope: ReplayEquivalenceEnvelope,
        candidates: list[dict[str, Any]],
        belief_state: dict[str, float],
        resource_context: ResourceContext,
    ) -> dict[str, Any] | None:
        """Returns the single highest-utility experiment, or None if stopping."""
        pass


class ReplayExecutor(abc.ABC):
    @abc.abstractmethod
    def execute_replays(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pass


class DivergenceValidator(abc.ABC):
    @abc.abstractmethod
    def validate_divergence(
        self,
        replays: list[dict[str, Any]],
        envelope: ReplayEquivalenceEnvelope,
    ) -> DivergenceReport:
        """
        Compare original vs replay state.
        Validates causal reachability, tolerance rules, frozen-state constraints.
        Signals early termination if forbidden divergence nodes are reached.
        """
        pass


class BeliefModel(abc.ABC):
    @abc.abstractmethod
    def update_belief(
        self, state: IncidentState, replays: list[dict[str, Any]]
    ) -> dict[str, float]:
        pass

    @abc.abstractmethod
    def current_beliefs(self) -> dict[str, float]:
        pass

    @abc.abstractmethod
    def entropy(self) -> float:
        pass


class StoppingPolicy(abc.ABC):
    @abc.abstractmethod
    def is_sufficient(
        self,
        state: IncidentState,
        resource_context: ResourceContext,
        belief_model: BeliefModel,
        remaining_candidates: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        Returns (should_stop, reason).
        Evaluates: posterior confidence, margin, entropy convergence,
        next-best EIG, minimum evidence count, resource limits.
        No hard iteration cap as primary logic.
        """
        pass


class RecoveryCutSolver(abc.ABC):
    @abc.abstractmethod
    def solve(
        self, targets: list[FailureTarget], fault_sources: dict[str, float]
    ) -> CausalRecoveryCut:
        pass


class RecoveryValidator(abc.ABC):
    @abc.abstractmethod
    def validate(
        self,
        cut: CausalRecoveryCut,
        provided_capabilities: list[SignedCapability] | None = None,
    ) -> RecoveryValidationResult:
        pass


class PolicyEngine(abc.ABC):
    @abc.abstractmethod
    def authorize(
        self,
        validation_result: RecoveryValidationResult,
        capabilities: list[SignedCapability],
    ) -> bool:
        pass


class Ledger(abc.ABC):
    @abc.abstractmethod
    def record_certificate(self, certificate: dict[str, Any]) -> str:
        pass


class TransportabilityGate(abc.ABC):
    @abc.abstractmethod
    def evaluate(
        self,
        src: CausalEnvironmentDescriptor,
        tgt: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint,
    ) -> TransportabilityDecision:
        pass
