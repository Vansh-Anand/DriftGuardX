import asyncio
from typing import List, Optional
from apps.api.src.pipeline.real_rag import RealRAGPipeline
from packages.rag_pipeline.src.interfaces import RetrievedChunk

class FaultType:
    STALE_CORPUS = "stale_corpus"
    DROPPED_CHUNKS = "dropped_chunks"
    EMBEDDING_MISMATCH = "embedding_mismatch"
    RETRIEVER_TOPK_REGRESSION = "retriever_topk_regression"
    PROMPT_REGRESSION = "prompt_regression"
    MODEL_DRIFT = "model_drift"
    PROVIDER_TIMEOUT = "provider_timeout"
    MALFORMED_OUTPUT = "malformed_output"

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
            # We mock the retriever to filter out chunks that match a certain expected version
            pass # Usually requires replacing the retriever implementation dynamically
            
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

    def reset(self):
        """Restores original pipeline state."""
        self.pipeline.retriever = self._orig_retriever
        self.pipeline.llm = self._orig_llm
        self.pipeline.prompt_template = self._orig_prompt
        self.pipeline.top_k = self._orig_top_k
