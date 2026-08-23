import hashlib
import os
import time
import uuid
from typing import Any

from packages.contracts.src.models import ComponentType, ReplayStateManifest
from packages.rag_pipeline.src.interfaces import (
    ArtifactStore,
    LLMAdapter,
    RetrievedChunk,
    RetrieverAdapter,
)
from packages.trace_sdk.src.tracer import TraceContext, hash_payload


class RealRAGPipeline:
    def __init__(
        self,
        retriever: RetrieverAdapter,
        llm: LLMAdapter,
        prompt_template: str,
        artifact_store: ArtifactStore,
        top_k: int = 5,
        pipeline_id: uuid.UUID = uuid.UUID("00000000-0000-0000-AAAA-000000000003")
    ):
        self.retriever = retriever
        self.llm = llm
        self.prompt_template = prompt_template
        self.artifact_store = artifact_store
        self.top_k = top_k
        self.pipeline_id = pipeline_id
        self.prompt_hash = hashlib.sha256(prompt_template.encode()).hexdigest()

    async def execute(
        self,
        query: str,
        corpus_version_id: str,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        random_seed: int = 42
    ) -> dict[str, Any]:
        """
        Executes the real RAG pipeline with full tracing.
        Returns a structured answer and the resulting ReplayStateManifest.
        """
        overall_start = time.time()

        ctx = TraceContext(
            tenant_id=tenant_id,
            pipeline_id=self.pipeline_id,
            run_id=run_id
        )

        root_span = ctx.start_span("real_rag_pipeline")

        retriever_span = ctx.start_span("retriever", parent_span_id=root_span.span_id)
        retriever_span.set_component(ComponentType.RETRIEVER, uuid.uuid4(), "real-v1")
        retriever_span.set_input({"query": query, "corpus_version_id": corpus_version_id, "top_k": self.top_k})

        # 1. Hybrid Retrieval
        chunks: list[RetrievedChunk] = await self.retriever.retrieve(
            query=query,
            corpus_version_id=corpus_version_id,
            top_k=self.top_k
        )

        chunk_ids = [c.chunk_id for c in chunks]
        retriever_span.set_output({"chunk_ids": chunk_ids})
        ctx.record_span(retriever_span.build())

        llm_span = ctx.start_span("llm_generator", parent_span_id=root_span.span_id)
        llm_span.set_component(ComponentType.GENERATOR, uuid.uuid4(), "real-v1")
        llm_span.set_input({"prompt_hash": self.prompt_hash, "context_chunk_ids": chunk_ids})

        # 2. LLM Generation
        llm_response = await self.llm.generate(
            prompt=self.prompt_template.format(query=query),
            context=chunks
        )

        llm_span.set_output({"text": llm_response["text"]})
        llm_span.set_tokens(llm_response.get("tokens_input", 0), llm_response.get("tokens_output", 0))
        ctx.record_span(llm_span.build())

        overall_latency_ms = (time.time() - overall_start) * 1000
        root_span.set_output({"final_text": llm_response["text"]})
        root_span._latency_ms = overall_latency_ms
        root_span._status_code = "OK"
        recorded_root = root_span.build()
        ctx.record_span(recorded_root)

        # 3. Format citations
        citations = []
        for i, c in enumerate(chunks):
            citations.append({
                "citation_id": i + 1,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "score": c.score
            })

        chunk_ids = [c.chunk_id for c in chunks]

        # Save Trace
        trace_data = {
            "spans": [s.model_dump() for s in ctx.get_spans()],
            "root_span_id": recorded_root.span_id
        }
        await self.artifact_store.save_trace(str(run_id), trace_data)

        # Build ReplayStateManifest
        manifest = ReplayStateManifest(
            run_id=run_id,
            tenant_id=tenant_id,
            original_query_hash=hash_payload(query),
            corpus_version_id=corpus_version_id,
            model_provider="simulated" if not llm_response.get("model_metadata") else llm_response["model_metadata"].get("provider", "unknown"),
            model_identifier="simulated" if not llm_response.get("model_metadata") else llm_response["model_metadata"].get("model", "unknown"),
            model_config_hash="default_config",
            prompt_template_hash=self.prompt_hash,
            retriever_version="pgvector-v1",
            retriever_settings={"top_k": self.top_k},
            retrieved_chunk_ids=chunk_ids,
            embedding_model_version="sbert-v1",
            vector_index_snapshot_id=corpus_version_id, # for real RAG, they are bound
            tool_schemas_hash="none",
            policy_config_hash="none",
            memory_snapshot_id="none",
            random_seed=random_seed,
            container_image_digest=os.environ.get("IMAGE_DIGEST", "dev-local"),
            dependency_lockfile_hash="mock_pip_hash",
            trace_root_hash=recorded_root.span_id
        )

        return {
            "answer": llm_response["text"],
            "chunk_ids": chunk_ids,
            "citations": citations,
            "latency_ms": overall_latency_ms,
            "tokens": {
                "input": llm_response.get("tokens_input", 0),
                "output": llm_response.get("tokens_output", 0),
                "total": llm_response.get("tokens_input", 0) + llm_response.get("tokens_output", 0)
            },
            "cost_usd": llm_response.get("cost_usd", 0.0),
            "model_metadata": llm_response.get("model_metadata", {}),
            "prompt_hash": self.prompt_hash,
            "corpus_version_id": corpus_version_id,
            "manifest": manifest
        }
