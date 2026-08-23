"""
Unit tests: Full-state ReplayEquivalenceEnvelope model.
Verifies HMAC envelope hash computation, field binding, and tamper detection.
"""
import os
import pytest

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-key")

from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    FaultSource,
    OptimizationMethod,
    ReplayEquivalenceEnvelope,
)


def _make_cut() -> CausalRecoveryCut:
    return CausalRecoveryCut(
        fault_sources=[FaultSource(node_id="retriever", probability=0.9)],
        failure_targets=[FailureTarget(node_id="output", failure_type="degradation", severity="high")],
        selected_actions=[],
        optimization_method=OptimizationMethod.EXACT,
        evidence_hash="abc123",
    )


def test_envelope_computes_hash_on_construction():
    env = ReplayEquivalenceEnvelope(
        trace_id="trace-001",
        recovery_cut=_make_cut(),
        invariants=[],
    )
    assert env.envelope_hash != "", "Envelope hash must be computed on construction"
    assert len(env.envelope_hash) == 64, "HMAC-SHA256 hex digest should be 64 chars"


def test_envelope_hash_is_stable():
    cut = _make_cut()
    env1 = ReplayEquivalenceEnvelope(trace_id="trace-001", recovery_cut=cut, invariants=[])
    env2 = ReplayEquivalenceEnvelope(trace_id="trace-001", recovery_cut=cut, invariants=[])
    assert env1.envelope_hash == env2.envelope_hash, "Same inputs must produce same hash"


def test_envelope_verify_passes():
    env = ReplayEquivalenceEnvelope(
        trace_id="trace-001",
        recovery_cut=_make_cut(),
        invariants=[],
        frozen_variables={"node_a": "hash_abc"},
        policy_binding="policy-hash-xyz",
    )
    assert env.verify_envelope_hash(), "verify_envelope_hash should return True for unmodified envelope"


def test_envelope_hash_changes_with_different_trace_id():
    cut = _make_cut()
    env1 = ReplayEquivalenceEnvelope(trace_id="trace-001", recovery_cut=cut, invariants=[])
    env2 = ReplayEquivalenceEnvelope(trace_id="trace-002", recovery_cut=cut, invariants=[])
    assert env1.envelope_hash != env2.envelope_hash, "Different trace_id must produce different hash"


def test_envelope_hash_changes_with_different_frozen_vars():
    cut = _make_cut()
    env1 = ReplayEquivalenceEnvelope(
        trace_id="t", recovery_cut=cut, invariants=[],
        frozen_variables={"node_a": "hash_1"},
    )
    env2 = ReplayEquivalenceEnvelope(
        trace_id="t", recovery_cut=cut, invariants=[],
        frozen_variables={"node_a": "hash_DIFFERENT"},
    )
    assert env1.envelope_hash != env2.envelope_hash


def test_envelope_exogenous_variables_stored():
    env = ReplayEquivalenceEnvelope(
        trace_id="t",
        recovery_cut=_make_cut(),
        invariants=[],
        exogenous_variables={"rng_seed": 42, "frozen_time_iso": "2024-01-01T00:00:00Z"},
    )
    assert env.exogenous_variables["rng_seed"] == 42
    assert env.exogenous_variables["frozen_time_iso"] == "2024-01-01T00:00:00Z"


def test_envelope_allowed_descendants_and_forbidden_nodes():
    env = ReplayEquivalenceEnvelope(
        trace_id="t",
        recovery_cut=_make_cut(),
        invariants=[],
        allowed_causal_descendants=["generator", "output"],
        forbidden_divergence_nodes=["policy_gate"],
    )
    assert "generator" in env.allowed_causal_descendants
    assert "policy_gate" in env.forbidden_divergence_nodes
