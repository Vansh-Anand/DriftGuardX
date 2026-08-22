from typing import List, Optional
import uuid
from packages.contracts.src.models import ComponentType, SpanKind
from packages.rag_benchmark.src.rag_pipeline import RAGPipeline

class FaultInjector:
    """
    Injects controlled faults into the RAG pipeline for benchmarking.
    """
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline
        
    def inject_retrieval_fault(self, corrupted_corpus: List[str]):
        """
        Simulates a corrupted index or retrieval failure by replacing the corpus.
        """
        self.pipeline.retriever.corpus = corrupted_corpus
        self.pipeline.retriever.embeddings = [self.pipeline.retriever._embed(t) for t in corrupted_corpus]
        self.pipeline.version_tag = "v2-corrupted-index"
        
    def inject_prompt_fault(self, bad_prompt: str):
        """
        Simulates a bad prompt update that might induce hallucination.
        """
        self.pipeline.system_prompt = bad_prompt
        self.pipeline.version_tag = "v2-bad-prompt"
        
    def inject_model_fault(self, new_model_name: str, high_temperature: float = 1.5):
        """
        Simulates model configuration drift or fallback to a weaker model.
        """
        self.pipeline.llm.model_name = new_model_name
        self.pipeline.temperature = high_temperature
        self.pipeline.version_tag = "v2-bad-model"
        
    def inject_policy_fault(self):
        """
        Simulates a relaxed policy enforcer.
        """
        # Override the check method to always return True (unsafe)
        def loose_check(prompt: str, response: str, **kwargs) -> bool:
            # We still emit the span but it's always safe
            trace_ctx = kwargs.get("trace_ctx")
            builder = None
            if trace_ctx:
                builder = trace_ctx.start_span("policy_check", kind=SpanKind.INTERNAL)
                builder.set_component(ComponentType.POLICY_CHECK, uuid.UUID(int=3), "v2-loose-policy")
                builder.set_attribute("is_safe", True)
                builder.finish()
                trace_ctx.record_span(builder.build())
            return True
                
        self.pipeline.policy.check = loose_check
        self.pipeline.version_tag = "v2-loose-policy"

    def reset(self, original_corpus: List[str]):
        """
        Resets the pipeline to normal state.
        """
        self.pipeline.retriever.corpus = original_corpus
        self.pipeline.retriever.embeddings = [self.pipeline.retriever._embed(t) for t in original_corpus]
        self.pipeline.system_prompt = "You are a helpful assistant. Use the context."
        self.pipeline.llm.model_name = "mock-gpt-4o"
        self.pipeline.temperature = 0.7
        # Restore original policy check
        from packages.rag_benchmark.src.rag_pipeline import DummyPolicyEnforcer
        self.pipeline.policy = DummyPolicyEnforcer()
        self.pipeline.version_tag = "v1"
