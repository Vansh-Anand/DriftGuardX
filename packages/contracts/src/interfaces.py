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
)
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
)


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
    def build_envelope(self, incident_id: str, candidates: list[dict[str, Any]]) -> ReplayEquivalenceEnvelope:
        pass


class RAEBGateway(abc.ABC):
    @abc.abstractmethod
    def check_admissibility(self, envelope: ReplayEquivalenceEnvelope) -> bool:
        pass


class ExperimentPlanner(abc.ABC):
    @abc.abstractmethod
    def plan_experiments(self, envelope: ReplayEquivalenceEnvelope, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pass


class ReplayExecutor(abc.ABC):
    @abc.abstractmethod
    def execute_replays(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pass


class DivergenceValidator(abc.ABC):
    @abc.abstractmethod
    def validate_divergence(self, replays: list[dict[str, Any]]) -> bool:
        pass


class BeliefModel(abc.ABC):
    @abc.abstractmethod
    def update_belief(self, state: IncidentState, replays: list[dict[str, Any]]) -> dict[str, float]:
        pass


class StoppingPolicy(abc.ABC):
    @abc.abstractmethod
    def is_sufficient(self, state: IncidentState) -> bool:
        pass


class RecoveryCutSolver(abc.ABC):
    @abc.abstractmethod
    def solve(self, targets: list[FailureTarget], fault_sources: dict[str, float]) -> CausalRecoveryCut:
        pass


class RecoveryValidator(abc.ABC):
    @abc.abstractmethod
    def validate(self, cut: CausalRecoveryCut) -> RecoveryValidationResult:
        pass


class PolicyEngine(abc.ABC):
    @abc.abstractmethod
    def authorize(self, validation_result: RecoveryValidationResult) -> bool:
        pass


class Ledger(abc.ABC):
    @abc.abstractmethod
    def record_certificate(self, certificate: dict[str, Any]) -> str:
        pass


class TransportabilityGate(abc.ABC):
    @abc.abstractmethod
    def evaluate(self, src: CausalEnvironmentDescriptor, tgt: CausalEnvironmentDescriptor, footprint: RecoveryMechanismFootprint) -> TransportabilityDecision:
        pass
