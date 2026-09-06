import uuid
from unittest.mock import AsyncMock

import pytest

from packages.evaluation.src.retrieval_metrics import RetrievalEvaluator
from packages.rag_pipeline.src.adapters.postgres_retriever import (
    PgRetrievedChunk,
    PostgresHybridRetriever,
)


class DummyEmbeddingAdapter:
    async def embed(self, text: str) -> list[float]:
        # Deterministic pseudo-embedding based on string hash
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h[:16]]


class MockDBResult:
    def __init__(self, mappings_list):
        self._mappings = mappings_list

    def mappings(self):
        return self._mappings


@pytest.mark.asyncio
async def test_postgres_hybrid_retriever_initialization_and_tenant_scoping():
    tenant_a = uuid.uuid4()
    mock_session = AsyncMock()
    mock_session.bind = None

    retriever = PostgresHybridRetriever(
        db_session=mock_session,
        embedding_adapter=DummyEmbeddingAdapter(),
        tenant_id=tenant_a,
        k_rrf=60,
    )

    assert retriever.tenant_id == str(tenant_a)
    assert retriever.k_rrf == 60


@pytest.mark.asyncio
async def test_postgres_hybrid_retriever_tenant_isolation():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    mock_session = AsyncMock()
    mock_session.bind = None

    # Simulate DB execution: only return rows if tenant matches tenant_a
    async def mock_execute(sql, params):
        assert "tenant_id" in params
        req_tenant = params["tenant_id"]
        if req_tenant == tenant_a:
            return MockDBResult(
                [
                    {
                        "chunk_id": "c1",
                        "text_content": "Tenant A Secret Info",
                        "rrf_score": 0.032,
                        "document_id": "d1",
                    }
                ]
            )
        return MockDBResult([])

    mock_session.execute.side_effect = mock_execute

    retriever_a = PostgresHybridRetriever(
        db_session=mock_session,
        embedding_adapter=DummyEmbeddingAdapter(),
        tenant_id=tenant_a,
    )
    retriever_b = PostgresHybridRetriever(
        db_session=mock_session,
        embedding_adapter=DummyEmbeddingAdapter(),
        tenant_id=tenant_b,
    )

    # Querying tenant A yields tenant A's documents
    chunks_a = await retriever_a.retrieve("secret", "v1", top_k=5)
    assert len(chunks_a) == 1
    assert chunks_a[0].chunk_id == "c1"

    # Querying tenant B yields 0 documents (strict tenant isolation)
    chunks_b = await retriever_b.retrieve("secret", "v1", top_k=5)
    assert len(chunks_b) == 0


@pytest.mark.asyncio
async def test_retrieval_evaluator_metrics():
    # Setup a mock retriever with predictable results
    class StaticRetriever:
        async def retrieve(self, query: str, corpus_version_id: str, top_k: int):
            if "machine learning" in query:
                return [
                    PgRetrievedChunk("chunk-ml-1", "intro to ml", 0.9, "doc-1"),
                    PgRetrievedChunk("chunk-ml-2", "advanced ml", 0.8, "doc-2"),
                    PgRetrievedChunk("chunk-other", "irrelevant", 0.1, "doc-3"),
                ][:top_k]
            return [
                PgRetrievedChunk("chunk-net-1", "networks", 0.9, "doc-4"),
                PgRetrievedChunk("chunk-ml-1", "intro to ml", 0.3, "doc-1"),
            ][:top_k]

    evaluator = RetrievalEvaluator(k_values=[1, 2, 3])
    test_dataset = [
        {
            "query": "what is machine learning",
            "relevant_chunk_ids": ["chunk-ml-1", "chunk-ml-2"],
        },
        {
            "query": "deep neural networks",
            "relevant_chunk_ids": ["chunk-net-1"],
        },
    ]

    result = await evaluator.evaluate_retriever(StaticRetriever(), test_dataset)

    assert result.total_queries == 2
    assert result.recall_at_k[1] == 0.75  # (1/2 + 1/1) / 2 = 0.75
    assert result.recall_at_k[2] == 1.0  # Both found in top 2
    assert result.mrr == 1.0  # Both had top-1 hit
    assert result.ndcg_at_k[1] > 0.5
    assert result.latency_p50_ms >= 0.0
