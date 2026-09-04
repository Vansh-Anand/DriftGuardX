import uuid

from packages.contracts.src.models import ReplayStateManifest


def get_base_manifest():
    return ReplayStateManifest(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        original_query="mock_query",
        original_query_hash="hash_a",
        corpus_version_id="v1",
        model_provider="simulated",
        model_identifier="gpt-4",
        model_config_hash="conf_hash",
        prompt_template_hash="prompt_hash",
        retriever_version="pgvector",
        retriever_settings={"top_k": 5},
        retrieved_chunk_ids=["chunk1"],
        embedding_model_version="sbert",
        vector_index_snapshot_id="v1",
        tool_schemas_hash="none",
        policy_config_hash="none",
        memory_snapshot_id="none",
        random_seed=42,
        container_image_digest="digest",
        dependency_lockfile_hash="pip_hash",
        trace_root_hash="trace_hash",
    )


def test_manifest_is_fully_pinned():
    manifest = get_base_manifest()
    assert manifest.is_fully_pinned() is True


def test_manifest_missing_dependency():
    manifest = get_base_manifest()
    manifest.corpus_version_id = None
    assert manifest.is_fully_pinned() is False


def test_manifest_hash_changes_on_prompt_change():
    m1 = get_base_manifest()
    m1.prompt_template_hash = "hash_1"

    m2 = get_base_manifest()
    m2.prompt_template_hash = "hash_2"

    assert m1.compute_hash() != m2.compute_hash()


def test_manifest_hash_changes_on_index_change():
    m1 = get_base_manifest()
    m1.vector_index_snapshot_id = "v1"

    m2 = get_base_manifest()
    m2.vector_index_snapshot_id = "v2"

    assert m1.compute_hash() != m2.compute_hash()


def test_manifest_hash_changes_on_retriever_settings_change():
    m1 = get_base_manifest()
    m1.retriever_settings = {"top_k": 5}

    m2 = get_base_manifest()
    m2.retriever_settings = {"top_k": 10}

    assert m1.compute_hash() != m2.compute_hash()
