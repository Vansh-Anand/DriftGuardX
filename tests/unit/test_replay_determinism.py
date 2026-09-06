import datetime
import uuid

from packages.contracts.src.models import (
    ComponentType,
    ComponentVersion,
    ReplayStateManifest,
    RequestRun,
    SpanRecord,
    TraceArtifact,
)
from packages.contracts.src.recovery_models import InterventionSpec
from packages.replay.src.engine import ReplayEngine, VersionRegistry


def create_mock_run():
    return RequestRun(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
    )


def create_mock_trace(run):
    span1 = SpanRecord(
        trace_id="00000000000000000000000000000001",
        span_id="0000000000000001",
        name="root",
        start_time=datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC),
        tenant_id=run.tenant_id,
        pipeline_id=run.pipeline_id,
        run_id=run.id,
    )
    span2 = SpanRecord(
        trace_id="00000000000000000000000000000001",
        span_id="0000000000000002",
        parent_span_id="0000000000000001",
        name="retriever/v1",
        start_time=datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC),
        tenant_id=run.tenant_id,
        pipeline_id=run.pipeline_id,
        run_id=run.id,
        component_type=ComponentType.RETRIEVER,
        component_version_id=uuid.uuid4(),
        component_version_tag="v1",
    )
    return TraceArtifact(
        run_id=run.id,
        tenant_id=run.tenant_id,
        pipeline_id=run.pipeline_id,
        spans=[span1, span2],
        root_span_id=span1.span_id,
    )


def create_mock_manifest(run):
    return ReplayStateManifest(
        run_id=run.id,
        tenant_id=run.tenant_id,
        original_query="What is testing?",
        corpus_version_id="v1",
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="hash",
        prompt_template_hash="hash",
        retriever_version="v1",
        retriever_settings={"top_k": 5},
        retrieved_chunk_ids=["chunk1"],
        embedding_provider="openai",
        embedding_model_id="ada",
        embedding_model_version="v1",
        embedding_vector_dimension=1536,
        embedding_config_hash="hash",
        vector_index_snapshot_id="v1",
        tool_schemas_hash="hash",
        policy_config_hash="hash",
        memory_snapshot_id="v1",
        random_seed=42,
        generation_parameters={},
        container_image_digest="digest",
        dependency_lockfile_hash="hash",
        trace_root_hash="hash",
        original_query_hash="hash",
    )


def test_replay_engine_is_strictly_deterministic():
    run = create_mock_run()
    trace = create_mock_trace(run)
    manifest = create_mock_manifest(run)

    spec = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        current_version="v1",
        candidate_version="v2-exp",
        intervention_type="alternate_stable",
    )

    registry = VersionRegistry()
    registry.register(
        ComponentVersion(
            id=trace.spans[1].component_version_id,
            component_type=ComponentType.RETRIEVER,
            version_tag="v1",
            config_hash="h1",
        )
    )

    cv_v2 = ComponentVersion(
        id=uuid.uuid4(),
        component_type=ComponentType.RETRIEVER,
        version_tag="v2-exp",
        config_hash="h2",
    )
    registry.register(cv_v2)

    engine = ReplayEngine(registry)

    ep1, t1 = engine.execute_replay(
        original_run=run,
        original_trace=trace,
        intervention=spec,
        replay_version=cv_v2,
        original_reliability_vector={"faithfulness": 0.9},
        seed=42,
        manifest=manifest,
    )

    ep2, t2 = engine.execute_replay(
        original_run=run,
        original_trace=trace,
        intervention=spec,
        replay_version=cv_v2,
        original_reliability_vector={"faithfulness": 0.9},
        seed=42,
        manifest=manifest,
    )

    assert ep1.replay_reliability_vector == ep2.replay_reliability_vector
    assert ep1.replay_reliability_score == ep2.replay_reliability_score
    assert ep1.is_synthetic == ep2.is_synthetic
    assert ep1.is_synthetic is True  # We must be explicitly deterministic synthetic

    # Trace logic produces same lengths and fields except random IDs and timestamps
    assert len(t1.spans) == len(t2.spans)
    for i in range(len(t1.spans)):
        assert t1.spans[i].name == t2.spans[i].name
        assert t1.spans[i].kind == t2.spans[i].kind
        assert t1.spans[i].status_code == t2.spans[i].status_code
        assert t1.spans[i].component_type == t2.spans[i].component_type
        assert t1.spans[i].component_version_tag == t2.spans[i].component_version_tag
        assert t1.spans[i].input_hash == t2.spans[i].input_hash
        assert t1.spans[i].output_hash == t2.spans[i].output_hash


def test_different_intervention_spec_yields_different_hash():
    s1 = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        current_version="v1",
        candidate_version="v2-exp",
        intervention_type="alternate_stable",
        rollback_plan="planA",
        expected_cost=1.0,
    )
    s2 = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        current_version="v1",
        candidate_version="v2-exp",
        intervention_type="alternate_stable",
        rollback_plan="planB",
        expected_cost=1.0,
    )

    assert s1.hash_identity != s2.hash_identity

    s3 = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        current_version="v1",
        candidate_version="v2-exp",
        intervention_type="alternate_stable",
        rollback_plan="planA",
        expected_cost=1.0,
    )

    assert s1.hash_identity == s3.hash_identity

    s4 = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        current_version="v1",
        candidate_version="v3-exp",
        intervention_type="alternate_stable",
        rollback_plan="planA",
        expected_cost=1.0,
    )
    assert s1.hash_identity != s4.hash_identity
