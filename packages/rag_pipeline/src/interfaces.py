from typing import Any, Protocol


class RetrievedChunk(Protocol):
    chunk_id: str
    text_content: str
    score: float
    document_id: str
    metadata: dict[str, Any]


class RetrieverAdapter(Protocol):
    async def retrieve(
        self, query: str, corpus_version_id: str, top_k: int
    ) -> list[RetrievedChunk]: ...


class EmbeddingAdapter(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class LLMAdapter(Protocol):
    async def generate(self, prompt: str, context: list[RetrievedChunk]) -> dict[str, Any]:
        """
        Returns structured dict:
        {
            "text": str,
            "tokens_input": int,
            "tokens_output": int,
            "latency_ms": float,
            "cost_usd": float,
            "model_metadata": dict
        }
        """
        ...


class ArtifactStore(Protocol):
    async def save_trace(self, run_id: str, trace_data: dict[str, Any]) -> None: ...


class EvaluationProvider(Protocol):
    async def evaluate_reliability(self, answer: str, context: list[RetrievedChunk]) -> float: ...
