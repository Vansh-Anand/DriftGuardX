"""
DriftGuard-X v2 — Tests for Causal Recovery Transportability Gate
"""
from datetime import datetime

from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    StructuredCalibrationEvidence,
    TransportStatus,
)
from packages.policy.src.causal_transport_gate import CausalTransportGate
from packages.replay.src.causal_experiment_planner import (
    DivergenceFrontier,
    ResourceRiskPlanner,
    RiskLimitedSequentialCausalExperimentPlanner,
    StoppingRule,
)
from packages.replay.src.planner import ReplayPlanner

SECRET_KEY = "test_secret_key"

def _make_evidence() -> StructuredCalibrationEvidence:
    return StructuredCalibrationEvidence(
        metric="accuracy",
        sample_size=1000,
        confidence_level=0.95,
        dataset="test_set_1",
        time=datetime.utcnow(),
        evaluator="system",
        source_result=0.9
    )

def _make_descriptor(tenant_id="tenant_A", overrides=None) -> CausalEnvironmentDescriptor:
    base = dict(
        tenant_id=tenant_id,
        model="gpt-4",
        prompt="v1",
        retriever="bm25",
        memory="redis",
        tools=["search", "calc"],
        policy="strict",
        index="docs_v1",
        data_distribution_fingerprint="hash_A",
        execution_configuration={"timeout": 30},
        causal_graph_hash="graph_A",
        provenance_hash="prov_A",
        calibration_evidence=_make_evidence(),
    )
    if overrides:
        base.update(overrides)

    desc = CausalEnvironmentDescriptor(**base)
    desc.signature = desc.recompute_signature(SECRET_KEY)
    return desc

def _make_footprint() -> RecoveryMechanismFootprint:
    return RecoveryMechanismFootprint(
        recovery_id="rec_1",
        required_invariant_components=["guardrail"],
        required_invariant_edges=["model->guardrail"],
        required_policy_conditions={"policy": "strict"},
        required_data_conditions={},
        required_calibration_conditions={"min_confidence": 0.90}
    )

# --- TESTS ---

def test_1_identical_environment():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor()
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.DIRECTLY_TRANSPORTABLE

def test_2_different_prompt():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"prompt": "v2"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert "prompt" in decision.unknown_conditions

def test_3_different_model():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"model": "gpt-4-turbo"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert "model" in decision.unknown_conditions

def test_4_different_policy():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"policy": "relaxed"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    # Policy mismatch hits required_policy_conditions directly -> critical mismatch
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE
    assert "policy" in decision.violated_conditions

def test_5_different_retrieval_index():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"index": "docs_v2"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert "index" in decision.unknown_conditions

def test_6_different_data_distribution():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"data_distribution_fingerprint": "hash_B"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert "data_distribution" in decision.unknown_conditions

def test_7_missing_calibration():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"calibration_evidence": None})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.UNKNOWN

def test_8_one_resolvable_difference():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"retriever": "dense"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert len(decision.unknown_conditions) == 1

def test_9_multiple_unresolved_differences():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"retriever": "dense", "prompt": "v3", "index": "docs_v3"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert len(decision.unknown_conditions) == 3

def test_10_critical_mechanism_mismatch():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"data_distribution_fingerprint": "hash_Z"})
    ft = _make_footprint()
    ft.required_data_conditions = {"data_distribution": "hash_A"}

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE
    assert "data_distribution" in decision.violated_conditions

def test_11_cross_tenant_denied():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor(tenant_id="tenant_A")
    tgt = _make_descriptor(tenant_id="tenant_B")
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft, allow_cross_tenant=False)
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE

def test_12_forged_provenance():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor()
    tgt.signature = "invalid_signature"
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE

def test_13_target_validation_succeeds():
    planner = RiskLimitedSequentialCausalExperimentPlanner(ReplayPlanner())
    experiments = [
        {"target_variable": "prompt"},
        {"target_variable": "model"}
    ]
    frontier = DivergenceFrontier(variables=["prompt", "model"], max_divergence_allowed=0.5, current_divergence=0.1)
    resource = ResourceRiskPlanner(budget_usd=100.0, max_downtime_ms=1000, blast_radius_limit=0.5)
    rule = StoppingRule(max_experiments=2, min_information_gain=0.1, max_resource_cost=50.0)

    # Needs a mock envelope. We bypass the actual CausalRecoveryCut mock required in ReplayEquivalenceEnvelope
    # by using python mocking or just empty strings. We'll pass a mock object since Pydantic will complain.
    class MockEnvelope:
        trace_id = "trace_1"

    selected = planner.select_minimum_experiments(experiments, MockEnvelope(), frontier, resource, rule)
    # Gain should be 0.8 since both are in frontier
    assert len(selected) == 2
    assert selected[0]["expected_gain"] == 0.8

def test_14_target_validation_fails():
    # If stopping rule is too restrictive, it fails to find experiments
    planner = RiskLimitedSequentialCausalExperimentPlanner(ReplayPlanner())
    experiments = [
        {"target_variable": "unknown_var"},
    ]
    # unknown_var is not in frontier, gain will be 0.2
    frontier = DivergenceFrontier(variables=["prompt", "model"], max_divergence_allowed=0.5, current_divergence=0.1)
    resource = ResourceRiskPlanner(budget_usd=100.0, max_downtime_ms=1000, blast_radius_limit=0.5)

    # High min information gain required, so it fails to select the experiment
    rule = StoppingRule(max_experiments=2, min_information_gain=0.5, max_resource_cost=50.0)

    class MockEnvelope:
        trace_id = "trace_1"

    selected = planner.select_minimum_experiments(experiments, MockEnvelope(), frontier, resource, rule)
    assert len(selected) == 0
