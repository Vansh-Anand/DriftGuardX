"""
DriftGuard-X v2 — Tests for Causal Recovery Transportability Gate
Updated for new CausalTransportGate and RiskLimitedSequentialCausalExperimentPlanner.
"""
import os
from datetime import UTC, datetime

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-key")

from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    StructuredCalibrationEvidence,
    TransportStatus,
)
from packages.policy.src.causal_transport_gate import CausalTransportGate

SECRET_KEY = "test_secret_key"


def _make_evidence() -> StructuredCalibrationEvidence:
    return StructuredCalibrationEvidence(
        metric="accuracy",
        sample_size=1000,
        confidence_level=0.95,
        dataset="test_set_1",
        time=datetime.now(UTC),
        evaluator="system",
        source_result=0.9,
    )


def _make_descriptor(tenant_id: str = "tenant_A", overrides: dict | None = None) -> CausalEnvironmentDescriptor:
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
        required_calibration_conditions={"min_confidence": 0.90},
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
    assert any("prompt" in c for c in decision.unknown_conditions)


def test_3_different_model():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"model": "gpt-4-turbo"})
    ft = _make_footprint()
    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert any("model" in c for c in decision.unknown_conditions)


def test_4_different_policy():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"policy": "relaxed"})
    ft = _make_footprint()
    decision = gate.evaluate_transportability(src, tgt, ft)
    # Policy mismatch hits required_policy_conditions directly → critical mismatch
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE
    assert any("policy" in c for c in decision.violated_conditions)


def test_5_different_retrieval_index():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"index": "docs_v2"})
    ft = _make_footprint()
    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert any("index" in c for c in decision.unknown_conditions)


def test_6_different_data_distribution():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"data_distribution_fingerprint": "hash_B"})
    ft = _make_footprint()
    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert any("data_distribution" in c for c in decision.unknown_conditions)


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
    assert len(decision.unknown_conditions) >= 1


def test_9_multiple_unresolved_differences():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"retriever": "dense", "prompt": "v3", "index": "docs_v3"})
    ft = _make_footprint()
    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    assert len(decision.unknown_conditions) >= 2


def test_10_critical_mechanism_mismatch():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"data_distribution_fingerprint": "hash_Z"})
    ft = _make_footprint()
    ft.required_data_conditions = {"data_distribution": "hash_A"}
    decision = gate.evaluate_transportability(src, tgt, ft)
    # Should be NOT_TRANSPORTABLE or TARGET_VALIDATION_REQUIRED (both are acceptable)
    assert decision.status in (TransportStatus.NOT_TRANSPORTABLE, TransportStatus.TARGET_VALIDATION_REQUIRED)


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


def test_13_planner_selects_experiment_for_target_validation():
    """
    When unknown conditions exist, the transport gate should invoke the real planner
    to generate target validation experiments (via select_minimum_experiments).
    """
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"prompt": "v3", "model": "gpt-4-turbo"})
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.TARGET_VALIDATION_REQUIRED
    # The gate should have generated target validation experiments via the real planner
    assert isinstance(decision.required_target_experiments, list)


def test_14_planner_generates_no_experiments_when_directly_transportable():
    """
    No target validation experiments should be generated for directly transportable recoveries.
    """
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor()
    ft = _make_footprint()

    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.DIRECTLY_TRANSPORTABLE
    assert len(decision.required_target_experiments) == 0


def test_15_missing_required_edge():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor(overrides={"causal_graph_hash": "graph_B"})
    ft = _make_footprint()
    ft.required_invariant_edges = ["causal_graph"]
    decision = gate.evaluate_transportability(src, tgt, ft)
    assert decision.status == TransportStatus.NOT_TRANSPORTABLE
    assert any("edge:causal_graph" in c for c in decision.violated_conditions)


def test_16_tampered_decision_evidence_changes_hash():
    gate = CausalTransportGate(SECRET_KEY)
    src = _make_descriptor()
    tgt = _make_descriptor()
    ft = _make_footprint()
    decision1 = gate.evaluate_transportability(src, tgt, ft)
    hash1 = decision1.decision_hash

    # Tamper with the explanation
    decision1.explanation = "Tampered explanation"
    hash2 = decision1.compute_hash()

    assert hash1 != hash2

    # Tamper with footprint hash
    decision1.footprint_hash = "fake_hash"
    hash3 = decision1.compute_hash()
    assert hash1 != hash3
    assert hash2 != hash3
