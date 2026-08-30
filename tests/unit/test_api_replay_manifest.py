from types import SimpleNamespace
from uuid import uuid4

from apps.api.src.routes.runs import _build_replay_manifest
from apps.api.src.pipeline.mock_rag import RETRIEVER_V1


def test_api_replay_manifest_binds_real_runtime_artifacts(monkeypatch):
    monkeypatch.delenv("DGX_CONTAINER_IMAGE_DIGEST", raising=False)
    run = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        request_hash="a" * 64,
    )
    trace = SimpleNamespace(
        root_span_id="b" * 16,
        total_span_count=1,
        spans_json=[{"span_id": "b" * 16, "output_hash": "c" * 64}],
    )

    manifest = _build_replay_manifest(
        original_run=run,
        original_trace=trace,
        replay_version=RETRIEVER_V1,
        seed=42,
    )

    assert manifest.is_fully_pinned()
    assert manifest.original_query_hash == run.request_hash
    assert manifest.retrieved_chunk_ids == ["doc-001", "doc-002"]
    assert manifest.container_image_digest.startswith("local-process:sha256:")
    assert len(manifest.dependency_lockfile_hash or "") == 64
    assert len(manifest.trace_root_hash or "") == 64
    assert manifest.model_identifier == "MockGeneratorV1@v1"
    assert "mock" not in manifest.retriever_settings
    serialized = manifest.model_dump_json()
    for obsolete_placeholder in (
        "mock-query-hash",
        "mock-config-hash",
        "mock-container",
        "mock-lockfile",
        "mock-trace-hash",
    ):
        assert obsolete_placeholder not in serialized


def test_api_replay_manifest_uses_deployed_image_digest(monkeypatch):
    image_digest = "sha256:" + "d" * 64
    monkeypatch.setenv("DGX_CONTAINER_IMAGE_DIGEST", image_digest)
    manifest = _build_replay_manifest(
        original_run=SimpleNamespace(
            id=uuid4(), tenant_id=uuid4(), request_hash="a" * 64
        ),
        original_trace=SimpleNamespace(
            root_span_id="b" * 16, total_span_count=0, spans_json=[]
        ),
        replay_version=RETRIEVER_V1,
        seed=7,
    )
    assert manifest.container_image_digest == image_digest
