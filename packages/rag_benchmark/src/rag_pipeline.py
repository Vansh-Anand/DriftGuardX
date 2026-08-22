import uuid
import numpy as np
import time
from typing import List, Dict, Any, Optional

from packages.contracts.src.models import ComponentType, SpanKind
from packages.trace_sdk.src.tracer import TraceContext, SpanBuilder
import uuid

# ─── Dummy Vector Store ────────────────────────────────────────────────────────

class DummyRetriever:
    def __init__(self, corpus: List[str]):
        self.corpus = corpus
        # Create dummy embeddings (random seeded by text length to be deterministic)
        self.embeddings = [self._embed(t) for t in corpus]

    def _embed(self, text: str) -> np.ndarray:
        np.random.seed(len(text))
        return np.random.randn(64)

    def retrieve(self, query: str, top_k: int = 3, trace_ctx: Optional[TraceContext] = None) -> List[str]:
        builder = None
        if trace_ctx:
            builder = trace_ctx.start_span("retrieve", kind=SpanKind.CLIENT)
            builder.set_component(ComponentType.RETRIEVER, uuid.UUID(int=1), "v1")
            builder.set_attribute("query", query)
            builder.set_attribute("top_k", top_k)
            builder.set_attribute("corpus_size", len(self.corpus))
            builder.set_input(query)
            
        q_emb = self._embed(query)
        
        # Compute cosine similarity
        scores = []
        for emb in self.embeddings:
            sim = np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-9)
            scores.append(sim)
            
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results = [self.corpus[i] for i in top_indices]
        
        if builder:
            builder.set_attribute("retrieved_docs", len(results))
            builder.set_attribute("avg_score", float(np.mean([scores[i] for i in top_indices])))
            builder.set_output(results)
            builder.finish()
            trace_ctx.record_span(builder.build())
        return results


# ─── Dummy LLM ────────────────────────────────────────────────────────────────

class DummyLLM:
    def __init__(self, model_name: str = "mock-gpt-4o"):
        self.model_name = model_name

    def generate(self, prompt: str, temperature: float = 0.7, trace_ctx: Optional[TraceContext] = None) -> str:
        builder = None
        if trace_ctx:
            builder = trace_ctx.start_span("llm_generate", kind=SpanKind.CLIENT)
            builder.set_component(ComponentType.GENERATOR, uuid.UUID(int=2), "v1")
            builder.set_attribute("model", self.model_name)
            builder.set_attribute("temperature", temperature)
            builder.set_attribute("prompt_length", len(prompt))
            builder.set_input(prompt)
            
        # Simulate latency
        time.sleep(0.01)
        
        # Simple keyword matching to simulate generation
        response = "I don't have enough information to answer that."
        if "fault" in prompt.lower():
            response = "The system encountered a simulated fault in the retrieved context."
        elif "hello" in prompt.lower():
            response = "Hello! I am a simulated RAG pipeline."
        elif "drift" in prompt.lower():
            response = "DriftGuard-X monitors the behavior of agentic systems."
        else:
            response = f"Based on the context, I synthesized {len(prompt.split())} words of information."
            
        if builder:
            builder.set_attribute("response_length", len(response))
            builder.set_output(response)
            builder.finish()
            trace_ctx.record_span(builder.build())
        return response


# ─── Dummy Policy Enforcer ────────────────────────────────────────────────────

class DummyPolicyEnforcer:
    def check(self, prompt: str, response: str, trace_ctx: Optional[TraceContext] = None) -> bool:
        builder = None
        if trace_ctx:
            builder = trace_ctx.start_span("policy_check", kind=SpanKind.INTERNAL)
            builder.set_component(ComponentType.POLICY_CHECK, uuid.UUID(int=3), "v1")
            builder.set_input({"prompt": prompt, "response": response})
            
        is_safe = "classified" not in prompt.lower() and "classified" not in response.lower()
        
        if builder:
            builder.set_attribute("is_safe", is_safe)
            builder.set_output({"is_safe": is_safe})
            if not is_safe:
                builder.set_error("PolicyViolation", "classified data accessed")
            builder.finish()
            trace_ctx.record_span(builder.build())
            
        return is_safe


# ─── Full RAG Pipeline ────────────────────────────────────────────────────────

class RAGPipeline:
    """
    A controlled local RAG pipeline for benchmarking.
    """
    def __init__(
        self,
        corpus: List[str],
        model_name: str = "mock-gpt-4o",
        temperature: float = 0.7,
        system_prompt: str = "You are a helpful assistant. Use the context.",
    ):
        self.retriever = DummyRetriever(corpus)
        self.llm = DummyLLM(model_name)
        self.policy = DummyPolicyEnforcer()
        
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.version_tag = "v1"

    def run(self, query: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        run_id_val = uuid.UUID(run_id) if run_id else uuid.uuid4()
        tenant_id = uuid.UUID(int=0)
        pipeline_id = uuid.UUID(int=0)
        
        trace_ctx = TraceContext(
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            run_id=run_id_val
        )
        
        root_builder = trace_ctx.start_span("rag_pipeline_run", kind=SpanKind.SERVER)
        root_builder.set_component(ComponentType.AGENT, uuid.UUID(int=4), self.version_tag)
        root_builder.set_input(query)
        root_builder.set_attribute("query", query)
        
        # 1. Retrieve
        docs = self.retriever.retrieve(query, top_k=3, trace_ctx=trace_ctx)
        
        # 2. Build Prompt
        prompt_builder = trace_ctx.start_span("build_prompt", kind=SpanKind.INTERNAL)
        prompt_builder.set_component(ComponentType.MEMORY_READ, uuid.UUID(int=5), "v1")
        prompt_builder.set_input({"docs": docs, "query": query})
        
        context = "\n".join(docs)
        prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nQuery: {query}"
        
        prompt_builder.set_attribute("context_length", len(context))
        prompt_builder.set_output(prompt)
        prompt_builder.finish()
        trace_ctx.record_span(prompt_builder.build())
            
        # 3. Generate
        response = self.llm.generate(prompt, temperature=self.temperature, trace_ctx=trace_ctx)
        
        # 4. Policy Check
        is_safe = self.policy.check(prompt, response, trace_ctx=trace_ctx)
        
        if not is_safe:
            response = "I cannot fulfill this request due to safety policies."
            root_builder.set_error("SafetyPolicyBlocked", "Safety Policy Blocked Response")
        
        output = {
            "query": query,
            "response": response,
            "is_safe": is_safe,
            "run_id": str(run_id_val)
        }
        root_builder.set_output(output)
        root_builder.finish()
        trace_ctx.record_span(root_builder.build())
        
        return {
            "output": output,
            "trace_ctx": trace_ctx
        }
