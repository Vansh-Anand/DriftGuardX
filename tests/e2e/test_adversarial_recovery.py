from datetime import UTC, datetime, timedelta

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import FailureTarget
from packages.contracts.src.transport_models import TransportStatus
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
    MockStoppingPolicy,
    MockTraceProvider,
    MockTransportabilityGate,
)
from packages.recovery.src.orchestrator import CausalRecoveryOrchestrator


def _access_context() -> AccessContext:
    return AccessContext(
        requester_id="adversarial-test-operator",
        tenant_id="test-tenant",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


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
        stopping_policy=MockStoppingPolicy(),
        recovery_solver=MockRecoveryCutSolver(),
        recovery_validator=MockRecoveryValidator(),
        policy_engine=MockPolicyEngine(),
        ledger=MockLedger(),
        transport_gate=MockTransportabilityGate(),
    )
    defaults.update(overrides)
    return CausalRecoveryOrchestrator(**defaults)


def test_adversarial_replay_attack():
    """Test fake divergence: divergence_validator flags a failure, ensuring it fails closed."""
    orch = build_orchestrator(divergence_validator=MockDivergenceValidator(valid=False))
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]
    cert = orch.process_incident(state, targets, access_context=_access_context())
    assert not cert
    assert state.status == IncidentStatus.EVIDENCE_INSUFFICIENT


def test_adversarial_planner_attack_nan():
    """Test NaN telemetry or planner returning no valid experiments."""
    orch = build_orchestrator(
        experiment_planner=MockExperimentPlanner(experiments=[]),
        stopping_policy=MockStoppingPolicy(sufficient=False),
    )
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]
    cert = orch.process_incident(state, targets, access_context=_access_context())
    assert not cert
    assert state.status == IncidentStatus.EVIDENCE_INSUFFICIENT


def test_adversarial_stopping_attack():
    """Test low quality evidence stopping policy correctly failing closed."""
    orch = build_orchestrator(stopping_policy=MockStoppingPolicy(sufficient=False))
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high")]
    cert = orch.process_incident(state, targets, access_context=_access_context())
    assert not cert
    assert state.status == IncidentStatus.EVIDENCE_INSUFFICIENT


def test_adversarial_transport_attack_forged():
    """Test Transport Gate correctly rejecting forged provenance."""
    from packages.contracts.src.transport_models import (
        CausalEnvironmentDescriptor,
        RecoveryMechanismFootprint,
        TransportabilityDecision,
    )

    decision = TransportabilityDecision(
        recovery_id="rec_1",
        source_environment="env_a",
        target_environment="env_b",
        status=TransportStatus.NOT_TRANSPORTABLE,
        preserved_conditions=[],
        violated_conditions=["forged_provenance"],
        unknown_conditions=[],
        required_target_experiments=[],
        confidence_metadata={},
        explanation="Forged signature detected.",
        footprint_hash="forged-footprint-hash",
    )
    orch = build_orchestrator(transport_gate=MockTransportabilityGate(decision))

    src = CausalEnvironmentDescriptor(
        tenant_id="A",
        model="a",
        prompt="a",
        retriever="a",
        memory="a",
        tools=[],
        policy="a",
        index="a",
        data_distribution_fingerprint="a",
        execution_configuration={},
        causal_graph_hash="a",
        provenance_hash="a",
    )
    tgt = CausalEnvironmentDescriptor(
        tenant_id="B",
        model="b",
        prompt="b",
        retriever="b",
        memory="b",
        tools=[],
        policy="b",
        index="b",
        data_distribution_fingerprint="b",
        execution_configuration={},
        causal_graph_hash="b",
        provenance_hash="b",
    )
    ft = RecoveryMechanismFootprint(
        recovery_id="rec_1",
        required_invariant_components=[],
        required_invariant_edges=[],
        required_policy_conditions={},
        required_data_conditions={},
        required_calibration_conditions={},
    )

    res = orch.validate_transportability(src, tgt, ft)
    assert res.status == TransportStatus.NOT_TRANSPORTABLE
