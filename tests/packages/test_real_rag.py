import uuid
from unittest.mock import AsyncMock, patch

import pytest

from apps.api.src.pipeline.real_rag import RealPipelineProvenance, RealRAGPipeline
from packages.rag_pipeline.src.adapters.llm_adapter import SafeLLMAdapter
from packages.rag_pipeline.src.interfaces import RetrievedChunk


@pytest.fixture
def mock_retriever():
    retriever = AsyncMock()
    chunk = AsyncMock(spec=RetrievedChunk)
    chunk.chunk_id = "test-chunk-1"
    chunk.text_content = "This is a test chunk."
    chunk.score = 0.95
    chunk.document_id = "doc-1"
    retriever.retrieve.return_value = [chunk]
    return retriever

@pytest.mark.asyncio
async def test_safe_llm_adapter_fails_without_key():
    adapter = SafeLLMAdapter()

    with patch("apps.api.src.config.settings.llm_api_key", None):
        with pytest.raises(RuntimeError, match="LLM API Key missing"):
            await adapter.generate("Test prompt", [])

@pytest.mark.asyncio
async def test_real_rag_pipeline_structure(mock_retriever):
    adapter = SafeLLMAdapter()

    # Mocking the generate method directly so we don't need a real key during test
    adapter.generate = AsyncMock(return_value={
        "text": "Simulated answer",
        "tokens_input": 10,
        "tokens_output": 5,
        "latency_ms": 100,
        "cost_usd": 0.001,
        "model_metadata": {"model": "test-model", "provider": "test-provider"}
    })

    pipeline = RealRAGPipeline(
        retriever=mock_retriever,
        llm=adapter,
        prompt_template="Prompt: {query}",
        artifact_store=AsyncMock(),
        provenance=RealPipelineProvenance(
            retriever_version="pgvector-v1@sha256:abc",
            embedding_model_version="test-embedding-v1@sha256:def",
            vector_index_snapshot_id="index-v1@sha256:123",
            policy_config_hash="sha256:456",
            container_image_digest="sha256:789",
            dependency_lockfile_hash="sha256:abc123",
        ),
    )

    result = await pipeline.execute(
        query="What is testing?",
        corpus_version_id="v1",
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4()
    )

    assert "answer" in result
    assert result["answer"] == "Simulated answer"
    assert "chunk_ids" in result
    assert result["chunk_ids"] == ["test-chunk-1"]
    assert "citations" in result
    assert result["citations"][0]["chunk_id"] == "test-chunk-1"
    assert "tokens" in result
    assert result["tokens"]["total"] == 15
    assert "prompt_hash" in result
