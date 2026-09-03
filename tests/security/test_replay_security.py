"""
DriftGuard-X v2 — Replay Security Tests
Verifies replay engine bounds, timeouts, and resource limits.
"""

import concurrent.futures
import uuid

from packages.contracts.src.models import (
    ComponentType,
    ComponentVersion,
    Intervention,
    InterventionType,
    RequestRun,
    TraceArtifact,
)
from packages.replay.src.engine import ComponentExecutor, ReplayEngine, VersionRegistry


class HangingExecutor(ComponentExecutor):
    def execute(self, inputs, *, version, seed=42):
        import time

        # Simulate a network/LLM hang that never returns
        time.sleep(35)  # Longer than 30s timeout
        return {"output": "Should never reach here"}


class MassiveMemoryExecutor(ComponentExecutor):
    def execute(self, inputs, *, version, seed=42):
        # Return 6MB of text, which exceeds the 5MB bound
        return {"output": "A" * 6_000_000}


def test_replay_engine_timeout_enforcement():
    registry = VersionRegistry()
    registry.register(
        ComponentVersion(
            id=uuid.uuid4(),
            component_type=ComponentType.RETRIEVER,
            version_tag="v_hang",
            config_hash="dummy",
            is_active=True,
        )
    )

    # Patch the engine temporarily
    import packages.replay.src.engine as engine_module

    original_map = engine_module._EXECUTOR_MAP.copy()
    engine_module._EXECUTOR_MAP[(ComponentType.RETRIEVER, "v_hang")] = HangingExecutor()

    engine = ReplayEngine(registry)

    tenant_uuid = uuid.uuid4()
    pipeline_uuid = uuid.uuid4()

    dummy_run = RequestRun(
        id=uuid.uuid4(),
        tenant_id=tenant_uuid,
        pipeline_id=pipeline_uuid,
        request_hash="hash",
        reliability_vector={"total": 1.0},
    )
    dummy_trace = TraceArtifact(
        run_id=dummy_run.id,
        tenant_id=tenant_uuid,
        pipeline_id=pipeline_uuid,
        spans=[],
        root_span_id="root",
    )
    intervention = Intervention(
        run_id=dummy_run.id,
        tenant_id=tenant_uuid,
        intervention_type=InterventionType.ROLLBACK,
        target_component_type=ComponentType.RETRIEVER,
        from_version_id=uuid.uuid4(),
        to_version_id=uuid.uuid4(),
        from_version_tag="v_old",
        to_version_tag="v_hang",
        rationale="test",
    )

    # We patch concurrent.futures to simulate a timeout without actually waiting 30s
    class FakeFuture:
        def result(self, timeout=None):
            raise concurrent.futures.TimeoutError()

    class FakeExecutor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def submit(self, *args, **kwargs):
            return FakeFuture()

    original_executor = concurrent.futures.ThreadPoolExecutor
    concurrent.futures.ThreadPoolExecutor = lambda *args, **kwargs: FakeExecutor()

    try:
        from packages.contracts.src.models import ReplayStateManifest

        manifest = ReplayStateManifest(
            run_id=dummy_run.id,
            tenant_id=dummy_run.tenant_id,
            original_query_hash="mock-query",
            corpus_version_id="mock-corpus",
            model_provider="openai",
            model_identifier="gpt-4",
            model_config_hash="abc",
            prompt_template_hash="def",
            retriever_version="v1",
            retriever_settings={"mock": True},
            retrieved_chunk_ids=["chunk1"],
            embedding_model_version="v2",
            vector_index_snapshot_id="snapshot-1",
            tool_schemas_hash="tool-hash",
            policy_config_hash="policy-hash",
            memory_snapshot_id="memory-1",
            random_seed=42,
            container_image_digest="sha256:123",
            dependency_lockfile_hash="lock-hash",
            trace_root_hash="trace-hash",
        )
        episode, trace = engine.execute_replay(
            original_run=dummy_run,
            original_trace=dummy_trace,
            intervention=intervention,
            replay_version=registry.list_by_type(ComponentType.RETRIEVER)[0],
            original_reliability_vector={},
            request_inputs={},
            seed=42,
            manifest=manifest,
        )

        # Verify the engine caught the timeout and injected an error span
        retriever_span = next(s for s in trace.spans if s.component_type == ComponentType.RETRIEVER)
        assert retriever_span.error_type == "TimeoutError"
        assert "timeout limit" in retriever_span.error_message

    finally:
        engine_module._EXECUTOR_MAP = original_map
        concurrent.futures.ThreadPoolExecutor = original_executor


def test_replay_engine_memory_bound():
    registry = VersionRegistry()
    registry.register(
        ComponentVersion(
            id=uuid.uuid4(),
            component_type=ComponentType.RETRIEVER,
            version_tag="v_mem",
            config_hash="dummy",
            is_active=True,
        )
    )

    import packages.replay.src.engine as engine_module

    original_map = engine_module._EXECUTOR_MAP.copy()
    engine_module._EXECUTOR_MAP[(ComponentType.RETRIEVER, "v_mem")] = MassiveMemoryExecutor()

    engine = ReplayEngine(registry)

    tenant_uuid = uuid.uuid4()
    pipeline_uuid = uuid.uuid4()

    dummy_run = RequestRun(
        id=uuid.uuid4(),
        tenant_id=tenant_uuid,
        pipeline_id=pipeline_uuid,
        request_hash="hash",
        reliability_vector={"total": 1.0},
    )
    dummy_trace = TraceArtifact(
        run_id=dummy_run.id,
        tenant_id=tenant_uuid,
        pipeline_id=pipeline_uuid,
        spans=[],
        root_span_id="root",
    )
    intervention = Intervention(
        run_id=dummy_run.id,
        tenant_id=tenant_uuid,
        intervention_type=InterventionType.ROLLBACK,
        target_component_type=ComponentType.RETRIEVER,
        from_version_id=uuid.uuid4(),
        to_version_id=uuid.uuid4(),
        from_version_tag="v_old",
        to_version_tag="v_mem",
        rationale="test",
    )

    try:
        from packages.contracts.src.models import ReplayStateManifest

        manifest = ReplayStateManifest(
            run_id=dummy_run.id,
            tenant_id=dummy_run.tenant_id,
            original_query_hash="mock-query",
            corpus_version_id="mock-corpus",
            model_provider="openai",
            model_identifier="gpt-4",
            model_config_hash="abc",
            prompt_template_hash="def",
            retriever_version="v1",
            retriever_settings={"mock": True},
            retrieved_chunk_ids=["chunk1"],
            embedding_model_version="v2",
            vector_index_snapshot_id="snapshot-1",
            tool_schemas_hash="tool-hash",
            policy_config_hash="policy-hash",
            memory_snapshot_id="memory-1",
            random_seed=42,
            container_image_digest="sha256:123",
            dependency_lockfile_hash="lock-hash",
            trace_root_hash="trace-hash",
        )
        episode, trace = engine.execute_replay(
            original_run=dummy_run,
            original_trace=dummy_trace,
            intervention=intervention,
            replay_version=registry.list_by_type(ComponentType.RETRIEVER)[0],
            original_reliability_vector={},
            request_inputs={},
            seed=42,
            manifest=manifest,
        )

        retriever_span = next(s for s in trace.spans if s.component_type == ComponentType.RETRIEVER)
        assert retriever_span.error_type == "MemoryError"
        assert "resource bounds" in retriever_span.error_message

    finally:
        engine_module._EXECUTOR_MAP = original_map
