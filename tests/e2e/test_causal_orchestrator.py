"""
DriftGuard-X v2 — End-to-End Orchestrator Tests
PRIVATE — All Rights Reserved.
"""

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import FailureTarget, RecoveryValidationResult
from packages.contracts.src.transport_models import TransportStatus
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
        transport_gate=MockTransportabilityGate()
    )
    defaults.update(overrides)
    return CausalRecoveryOrchestrator(**defaults)


def test_scenario_a_bad_retriever():
    """Scenario A: Bad retriever version causes failure. Should fully recover."""
    orch = build_orchestrator()
    state = IncidentState()
    targets = [FailureTarget(node_id="llm", failure_type="hallucination", severity="high", evidence={"wrong_answer": True})]

    cert = orch.process_incident(state, targets)
    if not cert:
        print("Telemetry logs:", state.telemetry)
    assert cert.startswith("cert_")
    assert state.status == IncidentStatus.CLOSED


def test_scenario_b_poisoned_memory():
    """Scenario B: Poisoned memory -> fully recovers."""
    orch = build_orchestrator(
        intervention_generator=MockInterventionGenerator([{"target": "memory"}]),
        belief_model=MockBeliefModel({"memory": 0.99})
    )
    state = IncidentState()
    cert = orch.process_incident(state, [])
    assert cert.startswith("cert_")
    assert state.status == IncidentStatus.CLOSED


def test_scenario_c_wrong_prompt():
    """Scenario C: Wrong prompt version -> fully recovers."""
    orch = build_orchestrator(
        intervention_generator=MockInterventionGenerator([{"target": "prompt"}]),
        belief_model=MockBeliefModel({"prompt": 0.99})
    )
    state = IncidentState()
    cert = orch.process_incident(state, [])
    assert cert.startswith("cert_")
    assert state.status == IncidentStatus.CLOSED


def test_scenario_d_external_api_drift():
    """Scenario D: External API drift -> fails because we can't rollback external API (solver returns None)."""
    orch = build_orchestrator(
        recovery_solver=MockRecoveryCutSolver(cut=None)
    )
    state = IncidentState()
    cert = orch.process_incident(state, [])
    assert cert == ""
    assert state.status == IncidentStatus.RECOVERY_REJECTED


def test_scenario_e_tool_schema_mismatch():
    """Scenario E: Tool schema mismatch -> fails to validate capability/invariant."""
    from packages.contracts.src.recovery_models import CausalRecoveryCut, OptimizationMethod
    invalid_res = RecoveryValidationResult(
        recovery_cut=CausalRecoveryCut(
            fault_sources=[],
            failure_targets=[],
            selected_actions=[],
            optimization_method=OptimizationMethod.HEURISTIC,
            evidence_hash="mock_hash"
        ),
        failure_resolved=False,
        invariants=[],
        invariants_satisfied=False
    )
    orch = build_orchestrator(
        recovery_validator=MockRecoveryValidator(result=invalid_res)
    )
    state = IncidentState()
    cert = orch.process_incident(state, [])
    assert cert == ""
    assert state.status == IncidentStatus.RECOVERY_REJECTED


def test_scenario_f_cross_environment_transport_denied():
    """Scenario F: Cross-environment recovery attempt -> fails transport gate."""
    # First get the recovery certificate from a successful run
    orch = build_orchestrator()
    state = IncidentState()
    cert = orch.process_incident(state, [])
    assert cert.startswith("cert_")

    # Now try to transport it with a mock gate that rejects cross-environment
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
        violated_conditions=["cross_tenant"],
        unknown_conditions=[],
        required_target_experiments=[],
        confidence_metadata={},
        explanation="Denied"
    )
    orch.transport_gate = MockTransportabilityGate(decision)


    # We just need dummy descriptors
    src = CausalEnvironmentDescriptor(tenant_id="A", model="a", prompt="a", retriever="a", memory="a", tools=[], policy="a", index="a", data_distribution_fingerprint="a", execution_configuration={}, causal_graph_hash="a", provenance_hash="a")
    tgt = CausalEnvironmentDescriptor(tenant_id="B", model="a", prompt="a", retriever="a", memory="a", tools=[], policy="a", index="a", data_distribution_fingerprint="a", execution_configuration={}, causal_graph_hash="a", provenance_hash="a")
    ft = RecoveryMechanismFootprint(recovery_id="rec_1", required_invariant_components=[], required_invariant_edges=[], required_policy_conditions={}, required_data_conditions={}, required_calibration_conditions={})

    res = orch.validate_transportability(src, tgt, ft)
    assert res.status == TransportStatus.NOT_TRANSPORTABLE
