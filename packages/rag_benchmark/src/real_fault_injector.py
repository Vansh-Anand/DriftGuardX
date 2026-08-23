import asyncio

from apps.api.src.pipeline.real_rag import RealRAGPipeline


class FaultType:
    STALE_CORPUS = "stale_corpus"
    DROPPED_CHUNKS = "dropped_chunks"
    EMBEDDING_MISMATCH = "embedding_mismatch"
    RETRIEVER_TOPK_REGRESSION = "retriever_topk_regression"
    PROMPT_REGRESSION = "prompt_regression"
    MODEL_DRIFT = "model_drift"
    PROVIDER_TIMEOUT = "provider_timeout"
    MALFORMED_OUTPUT = "malformed_output"
    TOOL_SCHEMA_MISMATCH = "tool_schema_mismatch"
    POLICY_CHANGE = "policy_change"
    MEMORY_CONTAMINATION = "memory_contamination"
    DB_FAILURE = "db_failure"

class RealFaultInjector:
    """
    Injects controlled faults into the RealRAGPipeline.
    """
    def __init__(self, pipeline: RealRAGPipeline):
        self.pipeline = pipeline

        # Save original states for restoration
        self._orig_retriever = pipeline.retriever
        self._orig_llm = pipeline.llm
        self._orig_prompt = pipeline.prompt_template
        self._orig_top_k = pipeline.top_k

    def inject_fault(self, fault_type: str, metadata: dict = None):
        """Injects a specific fault into the pipeline."""
        metadata = metadata or {}

        if fault_type == FaultType.STALE_CORPUS:
            orig_retrieve = self.pipeline.retriever.retrieve
            async def stale_retrieve(query, corpus_version_id, top_k):
                class StaleChunk:
                    def __init__(self):
                        self.text_content = "DriftGuard-X is an outdated project that does not use cryptographically bound traces."
                        self.chunk_id = "stale_1"
                        self.document_id = "doc_stale"
                        self.score = 0.99
                        self.metadata = {}
                return [StaleChunk()]
            self.pipeline.retriever.retrieve = stale_retrieve

        elif fault_type == FaultType.DROPPED_CHUNKS:
            orig_retrieve = self.pipeline.retriever.retrieve
            async def broken_retrieve(query, corpus_version_id, top_k):
                res = await orig_retrieve(query, corpus_version_id, top_k)
                # Drop the first (most relevant) chunk
                return res[1:] if len(res) > 1 else []
            self.pipeline.retriever.retrieve = broken_retrieve

        elif fault_type == FaultType.RETRIEVER_TOPK_REGRESSION:
            self.pipeline.top_k = 1

        elif fault_type == FaultType.PROMPT_REGRESSION:
            self.pipeline.prompt_template = "Question: {query}\nBe extremely unhelpful and say I DONT KNOW."

        elif fault_type == FaultType.MODEL_DRIFT:
            # We overwrite the model_metadata property directly on the LLM mock
            if hasattr(self.pipeline.llm, "model_name"):
                self.pipeline.llm.model_name = "gpt-2-broken"

        elif fault_type == FaultType.PROVIDER_TIMEOUT:
            orig_generate = self.pipeline.llm.generate
            async def timeout_generate(prompt, context):
                await asyncio.sleep(0.1)
                raise TimeoutError("LLM Provider Timeout")
            self.pipeline.llm.generate = timeout_generate

        elif fault_type == FaultType.MALFORMED_OUTPUT:
            orig_generate = self.pipeline.llm.generate
            async def malformed_generate(prompt, context):
                res = await orig_generate(prompt, context)
                res["text"] = '{"invalid_json": true'
                return res
            self.pipeline.llm.generate = malformed_generate

        elif fault_type == FaultType.EMBEDDING_MISMATCH:
            orig_retrieve = self.pipeline.retriever.retrieve
            async def mismatch_retrieve(query, corpus_version_id, top_k):
                raise ValueError("Embedding dimension mismatch: expected 768, got 1536")
            self.pipeline.retriever.retrieve = mismatch_retrieve

        elif fault_type == FaultType.TOOL_SCHEMA_MISMATCH:
            orig_generate = self.pipeline.llm.generate
            async def tool_mismatch_generate(prompt, context):
                raise ValueError("Tool schema validation failed: missing required parameter 'query'")
            self.pipeline.llm.generate = tool_mismatch_generate

        elif fault_type == FaultType.POLICY_CHANGE:
            orig_generate = self.pipeline.llm.generate
            async def policy_generate(prompt, context):
                raise PermissionError("Policy violation: query blocked by safety filters.")
            self.pipeline.llm.generate = policy_generate

        elif fault_type == FaultType.MEMORY_CONTAMINATION:
            self.pipeline.prompt_template = "Context: User hates the product.\nQuestion: {query}"

        elif fault_type == FaultType.DB_FAILURE:
            orig_retrieve = self.pipeline.retriever.retrieve
            async def db_fail_retrieve(query, corpus_version_id, top_k):
                raise ConnectionError("Postgres/Redis connection refused.")
            self.pipeline.retriever.retrieve = db_fail_retrieve

    def reset(self):
        """Restores original pipeline state."""
        self.pipeline.retriever = self._orig_retriever
        self.pipeline.llm = self._orig_llm
        self.pipeline.prompt_template = self._orig_prompt
        self.pipeline.top_k = self._orig_top_k
