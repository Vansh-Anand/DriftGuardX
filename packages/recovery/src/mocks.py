"""
DriftGuard-X v2 — Orchestrator Mocks for Testing & Benchmarks
PRIVATE — All Rights Reserved.
"""
import uuid
from typing import Any

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.interfaces import (
    BeliefModel,
    DivergenceValidator,
    EnvelopeBuilder,
    ExperimentPlanner,
    GraphProvider,
    InterventionGenerator,
    Ledger,
    PolicyEngine,
    RAEBGateway,
    RecoveryCutSolver,
    RecoveryValidator,
    ReplayExecutor,
    StoppingPolicy,
    TraceProvider,
    TransportabilityGate,
)
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    OptimizationMethod,
    RecoveryAction,
    RecoveryValidationResult,
    ReplayEquivalenceEnvelope,
)
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
    TransportStatus,
)


class MockTraceProvider(TraceProvider):
    def get_trace(self, incident_id: str) -> dict[str, Any]:
        return {"hash": "trace_hash_123", "data": "dummy"}


class MockGraphProvider(GraphProvider):
    def get_causal_graph(self, incident_id: str) -> dict[str, Any]:
        return {"hash": "graph_hash_123", "edges": []}


class MockInterventionGenerator(InterventionGenerator):
    def __init__(self, candidates=None):
        self.candidates = candidates or [{"target": "retriever"}]
    def generate_candidates(self, incident_state: IncidentState) -> list[dict[str, Any]]:
        return self.candidates


class MockEnvelopeBuilder(EnvelopeBuilder):
    def build_envelope(self, incident_id: str, candidates: list[dict[str, Any]]) -> ReplayEquivalenceEnvelope:
        cut = CausalRecoveryCut(
            fault_sources=[],
            failure_targets=[],
            selected_actions=[],
            optimization_method=OptimizationMethod.HEURISTIC,
            evidence_hash="mock_hash"
        )
        return ReplayEquivalenceEnvelope(trace_id=str(incident_id), recovery_cut=cut, invariants=[])


class MockRAEBGateway(RAEBGateway):
    def __init__(self, admissible=True):
        self.admissible = admissible
    def check_admissibility(self, envelope: ReplayEquivalenceEnvelope) -> bool:
        return self.admissible


class MockExperimentPlanner(ExperimentPlanner):
    def __init__(self, experiments: list[dict[str, Any]] | None = None):
        self.experiments = experiments

    def plan_experiments(self, env: ReplayEquivalenceEnvelope, candidates: list[RecoveryAction]) -> list[dict[str, Any]]:
        if self.experiments is not None:
            return self.experiments
        return [{"id": str(uuid.uuid4()), "action": c} for c in candidates]


class MockReplayExecutor(ReplayExecutor):
    def __init__(self):
        self.replays_executed = 0
        self.tokens_used = 0

    def execute_replays(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.replays_executed += len(experiments)
        self.tokens_used += len(experiments) * 1500  # Arbitrary mock cost per replay
        return experiments


class MockDivergenceValidator(DivergenceValidator):
    def __init__(self, valid=True):
        self.valid = valid
    def validate_divergence(self, replays: list[dict[str, Any]]) -> bool:
        return self.valid


class MockBeliefModel(BeliefModel):
    def __init__(self, posterior=None):
        self.posterior = posterior or {"retriever": 0.95}
    def update_belief(self, state: IncidentState, replays: list[dict[str, Any]]) -> dict[str, float]:
        return self.posterior


class MockStoppingPolicy(StoppingPolicy):
    def __init__(self, sufficient=True):
        self.sufficient = sufficient
    def is_sufficient(self, state: IncidentState) -> bool:
        return self.sufficient


class MockRecoveryCutSolver(RecoveryCutSolver):
    def __init__(self, cut="DEFAULT"):
        if cut == "DEFAULT":
            self.cut = CausalRecoveryCut(
                fault_sources=[],
                failure_targets=[],
                selected_actions=[RecoveryAction(target_component="retriever", action_type="ROLLBACK", arguments={"version": "v6"})],
                optimization_method=OptimizationMethod.HEURISTIC,
                evidence_hash="mock_hash",
                total_change_cost=10.0,
                expected_downtime=100
            )
        else:
            self.cut = cut
    def solve(self, targets: list[FailureTarget], fault_sources: dict[str, float]) -> CausalRecoveryCut | None:
        return self.cut


class MockRecoveryValidator(RecoveryValidator):
    def __init__(self, result=None):
        if result is None:
            from packages.contracts.src.recovery_models import CausalRecoveryCut
            self.result = RecoveryValidationResult(
                recovery_cut=CausalRecoveryCut(
                    fault_sources=[],
                    failure_targets=[],
                    selected_actions=[],
                    optimization_method=OptimizationMethod.HEURISTIC,
                    evidence_hash="mock_hash"
                ),
                failure_resolved=True,
                invariants=[],
                invariants_satisfied=True
            )
        else:
            self.result = result
    def validate(self, cut: CausalRecoveryCut) -> RecoveryValidationResult:
        return self.result


class MockPolicyEngine(PolicyEngine):
    def __init__(self, authorized=True):
        self.authorized = authorized
    def authorize(self, validation_result: RecoveryValidationResult) -> bool:
        return self.authorized


class MockLedger(Ledger):
    def record_certificate(self, certificate: dict[str, Any]) -> str:
        return f"cert_{uuid.uuid4()}"


class MockTransportabilityGate(TransportabilityGate):
    def __init__(self, decision=None):
        self.decision = decision or TransportabilityDecision(
            recovery_id="rec_1",
            source_environment="env_a",
            target_environment="env_b",
            status=TransportStatus.DIRECTLY_TRANSPORTABLE,
            preserved_conditions=[],
            violated_conditions=[],
            unknown_conditions=[],
            required_target_experiments=[],
            confidence_metadata={},
            explanation="OK"
        )
    def evaluate(self, src: CausalEnvironmentDescriptor, tgt: CausalEnvironmentDescriptor, footprint: RecoveryMechanismFootprint) -> TransportabilityDecision:
        return self.decision
