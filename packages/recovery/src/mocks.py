"""
DriftGuard-X v2 — Orchestrator Mocks for Testing & Benchmarks
Updated to match new interface signatures.
PRIVATE — All Rights Reserved.
"""

import uuid
from typing import Any

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.interfaces import (
    BeliefModel,
    DivergenceReport,
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
    ResourceContext,
    ResourceEstimate,
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
    SignedCapability,
)
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
    TransportStatus,
)
from packages.memory.src.auth import AccessContext
from packages.replay.src.stopping_rule import StoppingOutcome


class MockTraceProvider(TraceProvider):
    def get_trace(self, incident_id: str) -> dict[str, Any]:
        return {"hash": "trace_hash_123", "data": "dummy"}


class MockGraphProvider(GraphProvider):
    def get_causal_graph(self, incident_id: str) -> dict[str, Any]:
        return {"hash": "graph_hash_123", "edges": []}


class MockInterventionGenerator(InterventionGenerator):
    def __init__(self, candidates: list[dict[str, Any]] | None = None) -> None:
        self.candidates = candidates or [
            {
                "candidate_id": "retriever",
                "target_variable": "retriever",
                "node_id": "retriever",
                "estimated_cost_usd": 0.05,
            }
        ]

    def generate_candidates(self, incident_state: IncidentState) -> list[dict[str, Any]]:
        return self.candidates


class MockEnvelopeBuilder(EnvelopeBuilder):
    def build_envelope(
        self, incident_id: str, candidates: list[dict[str, Any]]
    ) -> ReplayEquivalenceEnvelope:
        cut = CausalRecoveryCut(
            fault_sources=[],
            failure_targets=[],
            selected_actions=[],
            optimization_method=OptimizationMethod.HEURISTIC,
            evidence_hash="mock_hash",
        )
        return ReplayEquivalenceEnvelope(
            trace_id=str(incident_id),
            recovery_cut=cut,
            invariants=[],
        )


class MockRAEBGateway(RAEBGateway):
    def __init__(self, admissible: bool = True) -> None:
        self.admissible = admissible

    def check_admissibility(self, envelope: ReplayEquivalenceEnvelope) -> bool:
        return self.admissible


class MockExperimentPlanner(ExperimentPlanner):
    """
    Mock planner that returns candidates one-at-a-time, respecting ResourceContext.
    Tracks replays_executed and tokens_used for benchmark reporting.
    """

    def __init__(self, experiments: list[dict[str, Any]] | None = None) -> None:
        self._experiments = experiments
        self._index = 0
        self.replays_executed = 0
        self.tokens_used = 0

    def plan_next_experiment(
        self,
        envelope: ReplayEquivalenceEnvelope,
        candidates: list[dict[str, Any]],
        belief_state: dict[str, float],
        resource_context: ResourceContext,
    ) -> dict[str, Any] | None:
        if resource_context.budget_exhausted():
            return None
        if self._experiments is not None:
            if self._index >= len(self._experiments):
                return None
            exp = {**self._experiments[self._index], "envelope_id": envelope.trace_id}
            self._index += 1
        else:
            if self._index >= len(candidates):
                return None
            exp = {**candidates[self._index], "envelope_id": envelope.trace_id}
            self._index += 1

        cost = float(exp.get("estimated_cost_usd", 0.05))
        reservation = resource_context.reserve(ResourceEstimate(cost_usd=cost))
        if not reservation:
            return None
        exp["_reservation"] = reservation

        self.replays_executed += 1
        self.tokens_used += 1500
        return exp


class MockReplayExecutor(ReplayExecutor):
    def __init__(self) -> None:
        self.replays_executed = 0
        self.tokens_used = 0

    def execute_replays(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.replays_executed += len(experiments)
        self.tokens_used += len(experiments) * 1500
        return [
            {"status": "completed", "spans": [], "replay_spans": [], "original_spans": [], **e}
            for e in experiments
        ]


class MockDivergenceValidator(DivergenceValidator):
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def validate_divergence(
        self,
        replays: list[dict[str, Any]],
        envelope: ReplayEquivalenceEnvelope,
    ) -> DivergenceReport:
        return DivergenceReport(
            valid=self.valid,
            reason="" if self.valid else "Mock divergence failure.",
        )


class MockBeliefModel(BeliefModel):
    def __init__(self, posterior: dict[str, float] | None = None) -> None:
        self._posterior = posterior or {"retriever": 0.95}

    def update_belief(
        self, state: IncidentState, replays: list[dict[str, Any]]
    ) -> dict[str, float]:
        return self._posterior

    def current_beliefs(self) -> dict[str, float]:
        return self._posterior

    def entropy(self) -> float:
        import math

        h = 0.0
        for p in self._posterior.values():
            if p > 0:
                h -= p * math.log2(p)
        return max(0.0, h)


class MockStoppingPolicy(StoppingPolicy):
    def __init__(self, sufficient: bool = True) -> None:
        self.sufficient = sufficient
        self._call_count = 0

    def record_iteration(self, entropy: float) -> None:
        pass

    def is_sufficient(
        self,
        state: IncidentState,
        resource_context: ResourceContext,
        belief_model: BeliefModel,
        remaining_candidates: list[dict[str, Any]],
    ) -> tuple[bool, StoppingOutcome, str]:
        self._call_count += 1
        if self.sufficient:
            return True, StoppingOutcome.CONFIRMED, "Mock: sufficient after first check."
        return False, StoppingOutcome.UNRESOLVED, "Mock: not sufficient."


class MockRecoveryCutSolver(RecoveryCutSolver):
    def __init__(self, cut: CausalRecoveryCut | str = "DEFAULT") -> None:
        if cut == "DEFAULT":
            self.cut: CausalRecoveryCut | None = CausalRecoveryCut(
                fault_sources=[],
                failure_targets=[],
                selected_actions=[
                    RecoveryAction(
                        target_component="retriever",
                        action_type="ROLLBACK",
                        metadata={"version": "v6"},
                    )
                ],
                optimization_method=OptimizationMethod.HEURISTIC,
                evidence_hash="mock_hash",
                total_change_cost=10.0,
                expected_downtime=100,
            )
        else:
            self.cut = cut  # type: ignore[assignment]

    def solve(
        self, targets: list[FailureTarget], fault_sources: dict[str, float]
    ) -> CausalRecoveryCut | None:
        return self.cut


class MockRecoveryValidator(RecoveryValidator):
    def __init__(self, result: RecoveryValidationResult | None = None) -> None:
        if result is None:
            dummy_cut = CausalRecoveryCut(
                fault_sources=[],
                failure_targets=[],
                selected_actions=[],
                optimization_method=OptimizationMethod.HEURISTIC,
                evidence_hash="mock_hash",
            )
            self.result = RecoveryValidationResult(
                recovery_cut=dummy_cut,
                failure_resolved=True,
                invariants=[],
                invariants_satisfied=True,
                eligible_for_canary=True,
            )
        else:
            self.result = result

    def validate_cut(
        self,
        cut: CausalRecoveryCut,
        invariants: list[Any],
        trace_id: str,
        original_spans: list[Any],
        access_context: AccessContext,
        exogenous_variables: dict[str, Any] | None = None,
    ) -> RecoveryValidationResult:
        return self.result


class MockPolicyEngine(PolicyEngine):
    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized

    def authorize(
        self,
        validation_result: RecoveryValidationResult,
        capabilities: list[SignedCapability],
    ) -> bool:
        return self.authorized


class MockLedger(Ledger):
    def record_certificate(self, certificate: dict[str, Any]) -> str:
        return f"cert_{uuid.uuid4()}"


class MockTransportabilityGate(TransportabilityGate):
    def __init__(self, decision: TransportabilityDecision | None = None) -> None:
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
            explanation="OK",
            footprint_hash="mock-footprint-hash",
        )

    def evaluate(
        self,
        src: CausalEnvironmentDescriptor,
        tgt: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint,
    ) -> TransportabilityDecision:
        return self.decision
