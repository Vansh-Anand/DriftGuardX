import pytest
from datetime import datetime
from uuid import uuid4

from packages.contracts.src.execution_state import (
    ExecutionStateSnapshot,
    ExecutionStateValue,
    ExecutionVariableClass,
    hash_state_value,
)
from packages.contracts.src.envelope import (
    ReplayEquivalenceEnvelope,
    EquivalenceConstraint,
    EquivalenceConstraintType,
    CausalIntervention,
    CausalInterventionType,
)
from packages.contracts.src.exogenous import (
    ExogenousStateRecord,
    ExogenousSourceType,
    ExogenousReplayStrategy,
    ToolCallRecord,
    SideEffectClass,
)
from packages.contracts.src.divergence import DivergenceType
from packages.contracts.src.graph import CausalGraph, GraphNode, NodeType
from packages.replay.src.envelope_builder import (
    ReplayEquivalenceEnvelopeBuilder,
    EnvelopeValidationError,
)
from packages.replay.src.divergence_monitor import DivergenceFrontierMonitor

TS = datetime.fromisoformat("2026-08-01T12:00:00Z")
TRACE_ID = uuid4()
COMP_API = "hash_api_1"
COMP_DB = "hash_db_1"
COMP_TOOL = "hash_tool_1"

def _make_exogenous_snapshot() -> ExecutionStateSnapshot:
    """Create a snapshot containing various exogenous states."""
    # Build some values that the envelope builder classifies as EXOGENOUS based on source
    vals = [
        ExecutionStateValue(
            key="api_weather", value_hash=hash_state_value("Sunny"),
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="external_api_response_hash", timestamp=TS, component_id=COMP_API,
        ),
        ExecutionStateValue(
            key="random_seed", value_hash=hash_state_value(42),
            variable_class=ExecutionVariableClass.FROZEN,  # usually frozen
            source="custom", timestamp=TS, component_id=COMP_API,
        ),
        ExecutionStateValue(
            key="feature_flag_x", value_hash=hash_state_value(True),
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="custom", timestamp=TS, component_id=COMP_API,
        ),
        ExecutionStateValue(
            key="intervention_target", value_hash=hash_state_value("old_prompt"),
            variable_class=ExecutionVariableClass.INTERVENED,
            source="custom", timestamp=TS, component_id="comp_intervened",
        ),
        ExecutionStateValue(
            key="tool_write", value_hash=hash_state_value("success"),
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="custom", timestamp=TS, component_id=COMP_TOOL,
            metadata={"capture_failed": True}  # simulate missing capture
        )
    ]
    return ExecutionStateSnapshot(
        id=uuid4(), run_id=TRACE_ID, trace_id=TRACE_ID, tenant_id=uuid4(),
        captured_at=TS, values=vals
    )

def test_exogenous_records_created_by_builder():
    """Verify ReplayEquivalenceEnvelopeBuilder maps EXOGENOUS to ExogenousStateRecord"""
    snap = _make_exogenous_snapshot()
    builder = ReplayEquivalenceEnvelopeBuilder()
    intervention = CausalIntervention(
        component_id="comp_intervened",
        variable_key="intervention_target",
        intervention_type=CausalInterventionType.CUSTOM,
        original_value_hash=hash_state_value("old_prompt"),
        replacement_value_hash=hash_state_value("new_prompt"),
        reason="Test intervention"
    )
    env = builder.build(
        original_trace_id=TRACE_ID,
        causal_graph=CausalGraph(tenant_id=snap.tenant_id, nodes=[
            GraphNode(id="comp_intervened", type=NodeType.TOOL, label="comp_intervened")
        ], edges=[], run_id=TRACE_ID, trace_digest="0"*64),
        intervention=intervention,
        state_snapshot=snap,
        policy_version="1.0",
        tenant_id=snap.tenant_id,
        strict_mode=False
    )
    
    assert len(env.exogenous_variables) == 3
    api_rec = next(r for r in env.exogenous_variables if r.key == "api_weather")
    flag_rec = next(r for r in env.exogenous_variables if r.key == "feature_flag_x")
    tool_rec = next(r for r in env.exogenous_variables if r.key == "tool_write")
    
    # API was successfully captured (not missing) -> FREEZE_CAPTURED
    assert api_rec.replay_strategy == ExogenousReplayStrategy.FREEZE_CAPTURED
    # General exogenous -> FREEZE_CAPTURED (since not missing)
    assert flag_rec.replay_strategy == ExogenousReplayStrategy.FREEZE_CAPTURED
    # Tool write missing capture -> UNCONTROLLABLE in non-strict mode
    assert tool_rec.replay_strategy == ExogenousReplayStrategy.UNCONTROLLABLE

def test_builder_strict_mode_forbids_replay():
    """Verify strict_mode=True forces FORBID_REPLAY on missing captures and raises."""
    snap = _make_exogenous_snapshot()
    builder = ReplayEquivalenceEnvelopeBuilder()
    
    intervention = CausalIntervention(
        component_id="comp_intervened",
        variable_key="intervention_target",
        intervention_type=CausalInterventionType.CUSTOM,
        original_value_hash=hash_state_value("old_prompt"),
        replacement_value_hash=hash_state_value("new_prompt"),
        reason="Test intervention"
    )
    with pytest.raises(EnvelopeValidationError) as exc:
        builder.build(
            original_trace_id=TRACE_ID,
            causal_graph=CausalGraph(tenant_id=snap.tenant_id, nodes=[
            GraphNode(id="comp_intervened", type=NodeType.TOOL, label="comp_intervened")
        ], edges=[], run_id=TRACE_ID, trace_digest="0"*64),
            intervention=intervention,
            state_snapshot=snap,
            policy_version="1.0",
            tenant_id=snap.tenant_id,
            strict_mode=True
        )
    
    assert "FORBID_REPLAY strategy" in str(exc.value)
    assert "tool_write" in str(exc.value)

def test_tool_call_record_validation():
    """Verify ToolCallRecord validates hashes and allows proper instantiation."""
    # valid
    tcr = ToolCallRecord(
        state_id="tool_1", key="my_tool", source_type=ExogenousSourceType.TOOL,
        source_identifier="calculator",
        tool_identity="calc_v1",
        input_hash=hash_state_value("2+2"),
        output_hash=hash_state_value("4"),
        side_effect_class=SideEffectClass.READ_ONLY,
        replay_strategy=ExogenousReplayStrategy.DETERMINISTIC_STUB
    )
    assert tcr.input_hash == hash_state_value("2+2")
    
    # invalid hash
    with pytest.raises(ValueError):
        ToolCallRecord(
            state_id="tool_1", key="my_tool", source_type=ExogenousSourceType.TOOL,
            source_identifier="calculator",
            tool_identity="calc_v1",
            input_hash="not_a_hash",
            replay_strategy=ExogenousReplayStrategy.DETERMINISTIC_STUB
        )

def test_divergence_monitor_uncontrollable_strategy():
    """Verify DivergenceMonitor handles exogenous divergence correctly."""
    snap = _make_exogenous_snapshot()
    builder = ReplayEquivalenceEnvelopeBuilder()
    # Remove the tool_write missing one to avoid UNCONTROLLABLE for that
    snap.values = [v for v in snap.values if v.key != "tool_write"]
    
    intervention = CausalIntervention(
        component_id="comp_intervened",
        variable_key="intervention_target",
        intervention_type=CausalInterventionType.CUSTOM,
        original_value_hash=hash_state_value("old_prompt"),
        replacement_value_hash=hash_state_value("new_prompt"),
        reason="Test intervention"
    )
    env = builder.build(
        original_trace_id=TRACE_ID,
        causal_graph=CausalGraph(tenant_id=snap.tenant_id, nodes=[
            GraphNode(id="comp_intervened", type=NodeType.TOOL, label="comp_intervened")
        ], edges=[], run_id=TRACE_ID, trace_digest="0"*64),
        intervention=intervention,
        state_snapshot=snap,
        policy_version="1.0",
        tenant_id=snap.tenant_id,
        strict_mode=False
    )
    
    # Manually override the strategy to UNCONTROLLABLE for api_weather
    for i, ex in enumerate(env.exogenous_variables):
        if ex.key == "api_weather":
            env.exogenous_variables[i].replay_strategy = ExogenousReplayStrategy.UNCONTROLLABLE
    env.envelope_hash = env._compute_hash()
    
    monitor = DivergenceFrontierMonitor(env)
    
    # Original
    orig_api = snap.get_value("api_weather")
    
    # Replay diverged
    rep_api = orig_api.model_copy(deep=True)
    rep_api.value_hash = hash_state_value("Rainy")
    
    obs = monitor.observe(orig_api, rep_api)
    
    # UNCONTROLLABLE allows divergence and records it as PERMITTED_EXOGENOUS_CHANGE
    assert obs.divergence_type == DivergenceType.PERMITTED_EXOGENOUS_CHANGE
    assert monitor.is_valid is True

def test_divergence_monitor_forbid_replay_strategy():
    """Verify DivergenceMonitor invalidates replay if a FORBID_REPLAY variable diverges."""
    snap = _make_exogenous_snapshot()
    snap.values = [v for v in snap.values if v.key != "tool_write"]
    builder = ReplayEquivalenceEnvelopeBuilder()
    intervention = CausalIntervention(
        component_id="comp_intervened",
        variable_key="intervention_target",
        intervention_type=CausalInterventionType.CUSTOM,
        original_value_hash=hash_state_value("old_prompt"),
        replacement_value_hash=hash_state_value("new_prompt"),
        reason="Test intervention"
    )
    env = builder.build(
        original_trace_id=TRACE_ID,
        causal_graph=CausalGraph(tenant_id=snap.tenant_id, nodes=[
            GraphNode(id="comp_intervened", type=NodeType.TOOL, label="comp_intervened")
        ], edges=[], run_id=TRACE_ID, trace_digest="0"*64),
        intervention=intervention,
        state_snapshot=snap,
        policy_version="1.0",
        tenant_id=snap.tenant_id,
        strict_mode=False
    )
    
    for i, ex in enumerate(env.exogenous_variables):
        if ex.key == "api_weather":
            env.exogenous_variables[i].replay_strategy = ExogenousReplayStrategy.FORBID_REPLAY
    env.envelope_hash = env._compute_hash()
    
    monitor = DivergenceFrontierMonitor(env)
    
    orig_api = snap.get_value("api_weather")
    rep_api = orig_api.model_copy(deep=True)
    rep_api.value_hash = hash_state_value("Rainy")
    
    obs = monitor.observe(orig_api, rep_api)
    
    # FORBID_REPLAY forbids divergence -> UNEXPECTED_DIVERGENCE
    assert obs.divergence_type == DivergenceType.UNEXPECTED_DIVERGENCE
    assert monitor.is_valid is False
