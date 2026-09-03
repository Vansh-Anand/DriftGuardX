from uuid import uuid4

from packages.contracts.src.models import ReplayStateManifest


def test_manifest_hashing_and_pinning():
    run_id = uuid4()
    tenant_id = uuid4()

    # Missing required state
    manifest = ReplayStateManifest(
        run_id=run_id,
        tenant_id=tenant_id,
    )
    assert manifest.is_fully_pinned() is False
    assert manifest.manifest_hash != ""

    # Fully pinned
    manifest_full = ReplayStateManifest(
        run_id=run_id,
        tenant_id=tenant_id,
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="abc",
        prompt_template_hash="def",
        retriever_version="v1",
        retriever_settings={"k": 5},
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
        original_query="test query",
        original_query_hash="query-hash",
        corpus_version_id="corpus-v1",
    )

    assert manifest_full.is_fully_pinned() is True

    # Test deterministic hash
    hash1 = manifest_full.compute_hash()
    hash2 = manifest_full.compute_hash()
    assert hash1 == hash2

    # Check exclude of transient fields
    manifest_full_2 = ReplayStateManifest(
        run_id=uuid4(),  # different run ID
        tenant_id=uuid4(),  # different tenant
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="abc",
        prompt_template_hash="def",
        retriever_version="v1",
        retriever_settings={"k": 5},
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
        original_query="test query",
        original_query_hash="query-hash",
        corpus_version_id="corpus-v1",
    )

    assert manifest_full.manifest_hash == manifest_full_2.manifest_hash
