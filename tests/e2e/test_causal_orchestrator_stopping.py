"""
Tests for orchestrator stopping logic.
"""

from datetime import UTC, datetime, timedelta

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import FailureTarget
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
    orch = build_orchestrator(belief_model=MockBeliefModel({"llm": 0.99}))  # High posterior
    orch.stopping_policy.min_replays = 0  # Allow stopping immediately

    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]

    cert = orch.process_incident(state, targets, access_context=_access_context())

    assert cert.startswith("cert_")
    assert state.status == IncidentStatus.CLOSED
    assert state.telemetry.get("stop_outcome") == "confirmed"
