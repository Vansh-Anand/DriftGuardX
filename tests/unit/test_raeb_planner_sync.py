import uuid
from datetime import UTC, datetime

import pytest

from packages.contracts.src.models import ComponentType, ReplayEpisode, SpanRecord, TraceArtifact
from packages.replay.src.belief_model import HeuristicLikelihoodEstimator, RootCauseBeliefModel
from packages.replay.src.causal_experiment_planner import (
    RiskLimitedSequentialCausalExperimentPlanner,
)
from packages.replay.src.raeb import RAEBGateway, resolve_intervention_node


def _mock_trace_with_spans(spans) -> TraceArtifact:
    return TraceArtifact(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        spans=spans,
        created_at=datetime.now(UTC)
    )

def test_A_B_ReplayEpisode_maps_exactly():
    # A. ReplayEpisode for retriever maps exactly to retriever span
    # B. Model intervention maps exactly to model span
    trace_id = "0" * 32
    tenant = uuid.uuid4()
    pipeline = uuid.uuid4()
    run = uuid.uuid4()
    span1 = SpanRecord(trace_id=trace_id, span_id="a" * 16, name="r", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.RETRIEVER)
    span2 = SpanRecord(trace_id=trace_id, span_id="b" * 16, name="m", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.GENERATOR)

    trace = _mock_trace_with_spans([span1, span2])

    # Test Retriever
    replay_r = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    assert resolve_intervention_node(replay_r, trace) == "a" * 16

    # Test Model
    replay_m = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.GENERATOR, # using Generator as model
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    # Patch component type for test
    trace.spans[1].component_type = "generator"
    assert resolve_intervention_node(replay_m, trace) == "b" * 16

def test_C_Duplicate_component_types_cause_ambiguity():
    trace_id = "0" * 32
    tenant = uuid.uuid4()
    pipeline = uuid.uuid4()
    run = uuid.uuid4()
    span1 = SpanRecord(trace_id=trace_id, span_id="a" * 16, name="r1", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.RETRIEVER)
    span2 = SpanRecord(trace_id=trace_id, span_id="b" * 16, name="r2", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.RETRIEVER)

    trace = _mock_trace_with_spans([span1, span2])
    replay = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    with pytest.raises(ValueError, match="Ambiguous component identity"):
        resolve_intervention_node(replay, trace)

    # With stable component_id provided
    class MockReplay:
        target_component_id = "b" * 16
        swapped_component_type = ComponentType.RETRIEVER
    assert resolve_intervention_node(MockReplay(), trace) == "b" * 16

def test_D_Missing_intervention_mapping_fails_closed():
    trace_id = "0" * 32
    tenant = uuid.uuid4()
    pipeline = uuid.uuid4()
    run = uuid.uuid4()
    span1 = SpanRecord(trace_id=trace_id, span_id="a" * 16, name="m", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.GENERATOR)

    trace = _mock_trace_with_spans([span1])
    replay = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    with pytest.raises(ValueError, match="Missing intervention mapping: no spans match"):
        resolve_intervention_node(replay, trace)

def test_E_Empty_trace_handled_safely():
    trace = _mock_trace_with_spans([])
    replay = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    with pytest.raises(ValueError, match="Missing intervention mapping: trace has no spans"):
        resolve_intervention_node(replay, trace)

def test_F_RAEB_posterior_produces_different_EIG():
    belief_uniform = RootCauseBeliefModel(components=["a", "b", "c"])
    belief_posterior = RootCauseBeliefModel(components=["a", "b", "c"])
    belief_posterior.beliefs = {"a": 0.9, "b": 0.05, "c": 0.05}

    est = HeuristicLikelihoodEstimator()
    eig_unif, _ = belief_uniform.expected_information_gain("a", est)
    eig_post, _ = belief_posterior.expected_information_gain("a", est)
    assert eig_unif != eig_post

def test_G_Planner_and_RAEB_return_consistent_EIG():
    belief = RootCauseBeliefModel(components=["a", "b", "c"])
    belief.beliefs = {"a": 0.5, "b": 0.3, "c": 0.2}

    est = HeuristicLikelihoodEstimator()
    # RAEB side raw EIG
    raeb_raw_eig, _ = belief.expected_information_gain("a", est)

    # Planner side
    planner = RiskLimitedSequentialCausalExperimentPlanner()
    eig_from_planner, _ = belief.expected_information_gain("a", planner._likelihood_estimator)

    assert raeb_raw_eig == eig_from_planner

def test_H_beliefs_always_sum_to_1():
    belief = RootCauseBeliefModel(components=["a", "b"])
    est = HeuristicLikelihoodEstimator()
    belief.update("a", "mitigated", est)
    assert sum(belief.beliefs.values()) == 1.0
    belief.update("b", "reproduced", est)
    assert sum(belief.beliefs.values()) == 1.0

def test_I_noninformative_intervention_EIG_approx_0():
    # If prior is near 1.0, info gain should be near 0
    belief = RootCauseBeliefModel(components=["a", "b"])
    belief.beliefs = {"a": 0.999, "b": 0.001}
    est = HeuristicLikelihoodEstimator()
    eig, _ = belief.expected_information_gain("a", est)
    assert eig < 0.05

def test_J_heuristic_estimator_metadata():
    trace_id = "0" * 32
    tenant = uuid.uuid4()
    pipeline = uuid.uuid4()
    run = uuid.uuid4()
    span1 = SpanRecord(trace_id=trace_id, span_id="a" * 16, name="r", start_time=datetime.now(UTC), tenant_id=tenant, pipeline_id=pipeline, run_id=run, component_type=ComponentType.RETRIEVER)

    trace = _mock_trace_with_spans([span1])
    replay = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )
    gateway = RAEBGateway()
    belief = RootCauseBeliefModel(components=["a"])
    from packages.replay.src.time_authority import TrustedTimestampEnvelope
    now = datetime.now(UTC)
    ts = TrustedTimestampEnvelope(timestamp=now, signature="mock", source="mock", issued_at=now, nonce="mock")
    eval_res = gateway.evaluate_admissibility(trace, replay, belief_model=belief, trusted_timestamp=ts)

    meta = eval_res.ig_estimator_metadata
    assert meta["estimator"] == "HeuristicLikelihoodEstimator"
    assert meta["is_calibrated"] is False

def test_K_no_mock_node_fallback():
    trace = _mock_trace_with_spans([])
    replay = ReplayEpisode(
        tenant_id=uuid.uuid4(), run_id=trace.run_id, swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(), replay_version_id=uuid.uuid4(), original_version_tag="v1", replay_version_tag="v2"
    )

    with pytest.raises(ValueError, match="Missing intervention mapping"):
        resolve_intervention_node(replay, trace)
