"""
Tests for packages/contracts/src/divergence.py
and packages/replay/src/divergence_monitor.py

Covers:
- intended retriever divergence;
- expected prompt-context change;
- unexpected model version change;
- unexpected policy change;
- changed tenant;
- changed permissions (authorization);
- changed random seed;
- external API change permitted;
- external API change prohibited;
- missing frozen value;
- nondeterministic latency within tolerance;
- latency outside tolerance;
- tampered envelope;
- fake replay attempting to mark unauthorized divergence valid.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from packages.contracts.src.divergence import (
    CausalDivergenceReport,
    DivergenceObservation,
    DivergenceType,
)
from packages.contracts.src.envelope import (
    CausalIntervention,
    CausalInterventionType,
    EquivalenceConstraint,
    EquivalenceConstraintType,
    ExogenousHandlingStrategy,
    ExogenousVariableSpec,
    ReplayEquivalenceEnvelope,
)
from packages.contracts.src.execution_state import (
    ExecutionStateSnapshot,
    ExecutionStateValue,
    ExecutionVariableClass,
    hash_state_value,
)
from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge, GraphNode, NodeType
from packages.replay.src.divergence_monitor import DivergenceFrontierMonitor
from packages.replay.src.envelope_builder import ReplayEquivalenceEnvelopeBuilder
from packages.replay.src.raeb import RAEBGateway
from packages.contracts.src.models import TraceArtifact, ReplayEpisode, SpanRecord, SpanKind, ComponentType, ReplayStatus


# ──────────────────────────────────────────────────────────────────────────────
# Shared Fixtures
# ──────────────────────────────────────────────────────────────────────────────

TENANT_ID = uuid4()
RUN_ID = uuid4()
TRACE_ID = uuid4()
TS = datetime(2024, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

RETRIEVER_CID = hashlib.sha256(b"retriever-01").hexdigest()
PROMPT_CID = hashlib.sha256(b"prompt-01").hexdigest()
MODEL_CID = hashlib.sha256(b"model-01").hexdigest()
POLICY_CID = hashlib.sha256(b"policy-01").hexdigest()


def _make_graph() -> CausalGraph:
    nodes = [
        GraphNode(id=RETRIEVER_CID, type=NodeType.RETRIEVER, label="retriever", features={"component_identity_hash": RETRIEVER_CID}),
        GraphNode(id=PROMPT_CID, type=NodeType.PROMPT, label="prompt", features={"component_identity_hash": PROMPT_CID}),
        GraphNode(id=MODEL_CID, type=NodeType.MODEL, label="model", features={"component_identity_hash": MODEL_CID}),
        GraphNode(id=POLICY_CID, type=NodeType.POLICY, label="policy", features={"component_identity_hash": POLICY_CID}),
    ]
    edges = [
        GraphEdge(id=f"{RETRIEVER_CID}->{PROMPT_CID}", source=RETRIEVER_CID, target=PROMPT_CID, type=EdgeType.DATA_DEPENDENCY),
        GraphEdge(id=f"{PROMPT_CID}->{MODEL_CID}", source=PROMPT_CID, target=MODEL_CID, type=EdgeType.DATA_DEPENDENCY),
        GraphEdge(id=f"{MODEL_CID}->{POLICY_CID}", source=MODEL_CID, target=POLICY_CID, type=EdgeType.CONTROL_FLOW),
    ]
    return CausalGraph(
        tenant_id=TENANT_ID, run_id=RUN_ID, nodes=nodes, edges=edges,
        trace_digest=hashlib.sha256(b"test-trace").hexdigest(),
    )


def _make_snapshot(extra_values: list[ExecutionStateValue] | None = None) -> ExecutionStateSnapshot:
    values = [
        ExecutionStateValue(
            key="retriever_config", value_hash=hash_state_value("v1"),
            variable_class=ExecutionVariableClass.FROZEN, source="retriever_config", timestamp=TS, component_id=RETRIEVER_CID,
        ),
        ExecutionStateValue(
            key="prompt_input", value_hash=hash_state_value("docs_v1"),
            variable_class=ExecutionVariableClass.DERIVED, source="prompt_hash", timestamp=TS, component_id=PROMPT_CID,
        ),
        ExecutionStateValue(
            key="model_version", value_hash=hash_state_value("gpt4"),
            variable_class=ExecutionVariableClass.FROZEN, source="model_version", timestamp=TS, component_id=MODEL_CID,
        ),
        ExecutionStateValue(
            key="policy_hash", value_hash=hash_state_value("policy-v1"),
            variable_class=ExecutionVariableClass.FROZEN, source="policy_hash", timestamp=TS, component_id=POLICY_CID,
        ),
        ExecutionStateValue(
            key="random_seed", value_hash=hash_state_value(42),
            variable_class=ExecutionVariableClass.FROZEN, source="random_seed", timestamp=TS,
        ),
        ExecutionStateValue(
            key="tenant_id", value_hash=hash_state_value(str(TENANT_ID)),
            variable_class=ExecutionVariableClass.FROZEN, source="tenant", timestamp=TS,
        ),
        ExecutionStateValue(
            key="authorization_context_hash", value_hash=hash_state_value("auth-user-1"),
            variable_class=ExecutionVariableClass.FROZEN, source="authorization_context_hash", timestamp=TS,
        ),
        ExecutionStateValue(
            key="latency_ms", value_hash=hash_state_value(150.0), metadata={"raw_value": 150.0},
            variable_class=ExecutionVariableClass.FROZEN, source="custom", timestamp=TS, component_id=MODEL_CID,
        ),
    ]
    if extra_values:
        values.extend(extra_values)
    return ExecutionStateSnapshot(
        run_id=RUN_ID, trace_id=TRACE_ID, tenant_id=TENANT_ID, captured_at=TS, values=values,
    )


def _make_envelope(
    intervention_key="retriever_config",
    intervention_comp=RETRIEVER_CID,
    extra_values=None,
    strict_mode=True,
    add_latency_tolerance=True,
) -> ReplayEquivalenceEnvelope:
    snapshot = _make_snapshot(extra_values)
    graph = _make_graph()
    orig_sv = snapshot.get_value(intervention_key)
    
    intervention = CausalIntervention(
        component_id=intervention_comp,
        variable_key=intervention_key,
        original_value_hash=orig_sv.value_hash,
        replacement_value_hash=hash_state_value("replacement"),
        intervention_type=CausalInterventionType.CHANGE_RETRIEVER,
        reason="test",
    )
    
    builder = ReplayEquivalenceEnvelopeBuilder()
    envelope = builder.build(
        original_trace_id=TRACE_ID, causal_graph=graph, intervention=intervention,
        state_snapshot=snapshot, policy_version="v1.0", tenant_id=TENANT_ID, strict_mode=strict_mode
    )
    
    if add_latency_tolerance:
        # Override the constraint for latency_ms to be TOLERANCE instead of EXACT_HASH
        for i, c in enumerate(envelope.equivalence_constraints):
            if c.variable_key == "latency_ms":
                envelope.equivalence_constraints[i] = EquivalenceConstraint(
                    variable_key="latency_ms", constraint_type=EquivalenceConstraintType.TOLERANCE, tolerance_value=50.0
                )
        # Re-sign the envelope
        envelope.envelope_hash = ""
        envelope.envelope_hash = envelope._compute_hash()
        
    return envelope, snapshot


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_intended_retriever_divergence():
    """Intervention variable changes -> EXPECTED_INTERVENTION"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("retriever_config")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("replacement")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.EXPECTED_INTERVENTION
    assert monitor.is_valid is True

def test_expected_prompt_context_change():
    """Descendant component variable changes -> EXPECTED_CAUSAL_DESCENDANT"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("prompt_input")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("docs_v2")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.EXPECTED_CAUSAL_DESCENDANT
    assert monitor.is_valid is True
    assert PROMPT_CID in monitor.frontier_components

def test_unexpected_model_version_change():
    """Frozen variable changes -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("model_version")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("gpt4-turbo")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False
    assert MODEL_CID in monitor.escaped_components
    assert "version" in monitor._invalidation_reason.lower() or "strict" in monitor._invalidation_reason.lower()

def test_unexpected_policy_change():
    """Security field changes -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("policy_hash")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("policy-v2")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_changed_tenant():
    """Tenant changes -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("tenant_id")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value(str(uuid4()))
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_changed_permissions():
    """Authorization context changes -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("authorization_context_hash")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("auth-user-2")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_changed_random_seed():
    """Random seed changes -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("random_seed")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value(99)
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_external_api_change_permitted():
    """Exogenous variable changes (UNCONTROLLABLE strategy) -> PERMITTED_EXOGENOUS_CHANGE"""
    extra = [ExecutionStateValue(
        key="weather_api", value_hash=hash_state_value("rain"),
        variable_class=ExecutionVariableClass.EXOGENOUS, source="external_api_response_hash", timestamp=TS,
        metadata={"capture_failed": True}
    )]
    env, snap = _make_envelope(extra_values=extra, strict_mode=False)
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("weather_api")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("sun")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.PERMITTED_EXOGENOUS_CHANGE
    assert monitor.is_valid is True

def test_external_api_change_prohibited():
    """Exogenous variable changes (REJECT_REPLAY strategy due to strict mode) -> UNEXPECTED_DIVERGENCE"""
    extra = [ExecutionStateValue(
        key="weather_api", value_hash=hash_state_value("rain"),
        variable_class=ExecutionVariableClass.EXOGENOUS, source="external_api_response_hash", timestamp=TS,
        metadata={"capture_failed": True}
    )]
    # This throws EnvelopeValidationError during build if strict_mode=True.
    # To test the monitor, we manually set the strategy to REJECT_REPLAY and bypass the builder strict check.
    env, snap = _make_envelope(extra_values=extra, strict_mode=False)
    for ev in env.exogenous_variables:
        if ev.variable_key == "weather_api":
            ev.strategy = ExogenousHandlingStrategy.REJECT_REPLAY
    env.envelope_hash = ""
    env.envelope_hash = env._compute_hash()
    
    monitor = DivergenceFrontierMonitor(env)
    orig = snap.get_value("weather_api")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("sun")
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_missing_frozen_value():
    """Replay doesn't provide a frozen value -> UNVERIFIABLE"""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("model_version")
    
    obs = monitor.observe(orig, None)
    assert obs.divergence_type == DivergenceType.UNVERIFIABLE
    # Monitor doesn't invalidate for UNVERIFIABLE by default, RAEB handles evidence downgrades
    assert monitor.is_valid is True

def test_nondeterministic_latency_within_tolerance():
    """Frozen variable changes within numeric tolerance -> PERMITTED_NONDETERMINISM"""
    env, snap = _make_envelope()
    if "latency_ms" in env.nondeterministic_variables:
        env.nondeterministic_variables.remove("latency_ms")
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("latency_ms")
    rep = orig.model_copy(deep=True)
    rep.metadata["raw_value"] = 180.0
    rep.value_hash = hash_state_value(180.0)
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.PERMITTED_NONDETERMINISM
    assert monitor.is_valid is True

def test_latency_outside_tolerance():
    """Frozen variable changes beyond numeric tolerance -> UNEXPECTED_DIVERGENCE"""
    env, snap = _make_envelope()
    if "latency_ms" in env.nondeterministic_variables:
        env.nondeterministic_variables.remove("latency_ms")
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("latency_ms")
    rep = orig.model_copy(deep=True)
    rep.metadata["raw_value"] = 250.0  # limit is 150 + 50 = 200
    rep.value_hash = hash_state_value(250.0)
    
    obs = monitor.observe(orig, rep)
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False

def test_tampered_envelope_monitor_init_fails():
    """Modifying envelope hash blocks monitor initialization."""
    env, snap = _make_envelope()
    object.__setattr__(env, "envelope_hash", "tampered-hash")
    
    with pytest.raises(ValueError, match="integrity check failed"):
        DivergenceFrontierMonitor(env)

def test_fake_replay_attempting_to_mark_unauthorized_divergence_valid():
    """A caller can't force the report to be valid if it diverged."""
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    orig = snap.get_value("model_version")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("hacked")
    monitor.observe(orig, rep)
    
    report = monitor.generate_report()
    assert report.valid is False
    assert not report.verify_integrity() is False
    
    # Try to tamper with report
    report.valid = True
    assert report.verify_integrity() is False


# ──────────────────────────────────────────────────────────────────────────────
# Integration with RAEB
# ──────────────────────────────────────────────────────────────────────────────

def test_raeb_divergence_integration():
    env, snap = _make_envelope()
    monitor = DivergenceFrontierMonitor(env)
    
    # Cause divergence
    orig = snap.get_value("model_version")
    rep = orig.model_copy()
    rep.value_hash = hash_state_value("hacked")
    monitor.observe(orig, rep)
    report = monitor.generate_report()
    
    trace = TraceArtifact(
        run_id=RUN_ID, tenant_id=TENANT_ID, pipeline_id=uuid4(), created_at=TS,
        spans=[SpanRecord(
            trace_id="a"*32, span_id="b"*16, name="root", kind=SpanKind.INTERNAL,
            start_time=TS, end_time=TS, tenant_id=TENANT_ID, pipeline_id=uuid4(), run_id=RUN_ID
        )]
    )
    replay = ReplayEpisode(
        tenant_id=TENANT_ID, run_id=RUN_ID, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid4(), replay_version_id=uuid4(),
        original_version_tag="v1", replay_version_tag="v2", status=ReplayStatus.COMPLETED
    )
    
    gateway = RAEBGateway(freshness_ttl_seconds=7200)
    eval_result = gateway.evaluate_with_envelope(
        live_trace=trace, proposed_replay=replay, envelope=env, 
        current_time=TS, divergence_report=report
    )
    
    assert eval_result.admissibility == "unsupported"
    assert "escaped frontier" in eval_result.rejection_reason
