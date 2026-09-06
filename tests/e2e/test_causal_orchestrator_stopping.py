"""
Tests for orchestrator stopping logic.
"""

from datetime import UTC, datetime, timedelta

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    OptimizationMethod,
    RecoveryValidationResult,
)
from packages.memory.src.auth import AccessContext
from packages.recovery.src.mocks import (
    MockBeliefModel,
    MockDivergenceValidator,
    MockEnvelopeBuilder,
    MockExperimentPlanner,
    MockGraphProvider,
    MockInterventionGenerator,
    MockLedger,
    MockPolicyEngine,
    MockRAEBGateway,
    MockRecoveryCutSolver,
    MockRecoveryValidator,
    MockReplayExecutor,
    MockTraceProvider,
    MockTransportabilityGate,
)
from packages.recovery.src.orchestrator import CausalRecoveryOrchestrator


def _access_context() -> AccessContext:
    return AccessContext(
        requester_id="stopping-test-operator",
        tenant_id="test-tenant",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


from packages.replay.src.stopping_rule import EvidentiaryStoppingRule


def build_orchestrator(**overrides):
    defaults = dict(
        trace_provider=MockTraceProvider(),
        graph_provider=MockGraphProvider(),
        intervention_generator=MockInterventionGenerator(),
        envelope_builder=MockEnvelopeBuilder(),
        raeb_gateway=MockRAEBGateway(),
        experiment_planner=MockExperimentPlanner(),
        replay_executor=MockReplayExecutor(),
        divergence_validator=MockDivergenceValidator(),
        belief_model=MockBeliefModel(),
        stopping_policy=EvidentiaryStoppingRule(),  # Use real stopping rule to test integration
        recovery_solver=MockRecoveryCutSolver(),
        recovery_validator=MockRecoveryValidator(),
        policy_engine=MockPolicyEngine(),
        ledger=MockLedger(),
        transport_gate=MockTransportabilityGate(),
    )
    defaults.update(overrides)
    return CausalRecoveryOrchestrator(**defaults)


def test_orchestrator_stops_and_fails_when_resource_exhausted():
    """RESOURCE_EXHAUSTED outcome fails closed."""
    orch = build_orchestrator(default_time_budget_seconds=0.0)  # instantly exhaust time budget
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]

    cert = orch.process_incident(state, targets, access_context=_access_context())

    assert cert == ""
    assert state.status == IncidentStatus.EVIDENCE_INSUFFICIENT
    assert state.telemetry.get("stop_outcome") == "resource_exhausted"


def test_orchestrator_stops_and_fails_when_planner_exhausted():
    """NO_ADMISSIBLE_EXPERIMENT outcome fails closed if planner returns None and not confirmed."""
    orch = build_orchestrator(experiment_planner=MockExperimentPlanner(experiments=[]))
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]

    cert = orch.process_incident(state, targets, access_context=_access_context())

    assert cert == ""
    assert state.status == IncidentStatus.EVIDENCE_INSUFFICIENT
    assert state.telemetry.get("stop_outcome") == "no_admissible_experiment"


def test_orchestrator_proceeds_when_confirmed():
    """CONFIRMED outcome proceeds to recovery planning."""

    dummy_cut = CausalRecoveryCut(
        fault_sources=[],
        failure_targets=[],
        selected_actions=[],
        optimization_method=OptimizationMethod.HEURISTIC,
        evidence_hash="mock_hash",
    )
    val_result = RecoveryValidationResult(
        recovery_cut=dummy_cut,
        failure_resolved=True,
        invariants=[],
        invariants_satisfied=True,
        eligible_for_canary=True,
    )
    orch = build_orchestrator(
        belief_model=MockBeliefModel({"llm": 0.99}),
        recovery_validator=MockRecoveryValidator(val_result),
    )  # High posterior
    orch.stopping_policy.min_replays = 0  # Allow stopping immediately

    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]

    cert = orch.process_incident(state, targets, access_context=_access_context())

    print("STATUS:", state.status)
    print("TELEMETRY:", state.telemetry)
    assert cert == ""
    assert state.status == IncidentStatus.RECOVERY_REJECTED
    assert state.telemetry.get("stop_outcome") == "confirmed"

    log_stages = [entry["to"] for entry in state.telemetry.get("transition_log", [])]
    assert IncidentStatus.RECOVERY_PLANNING in log_stages
    assert IncidentStatus.CANARY in log_stages
