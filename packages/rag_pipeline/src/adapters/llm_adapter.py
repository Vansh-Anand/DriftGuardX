import logging
import time
from typing import Any

from apps.api.src.config import settings
from packages.rag_pipeline.src.interfaces import LLMAdapter, RetrievedChunk

logger = logging.getLogger(__name__)


class SafeLLMAdapter(LLMAdapter):
    """
    LLM Adapter that uses real OpenAI API securely.
    """

    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.model_name = model_name
        # Note: Do not instantiate client here to avoid error if key is missing during init.

    async def generate(self, prompt: str, context: list[RetrievedChunk]) -> dict[str, Any]:
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None

        if not api_key:
            raise RuntimeError(
                "LLM API Key missing or unapproved. Cannot call external LLM provider."
            )

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI adapter dependency is unavailable; install the benchmark extra."
            ) from exc

        # Context building
        context_str = "\n\n".join(
            [f"[{i+1}] (Chunk: {c.chunk_id}) {c.text_content}" for i, c in enumerate(context)]
        )
        full_prompt = f"{prompt}\n\nContext:\n{context_str}\n\nPlease include citations to the context chunks using [N] format."

        start_time = time.time()

        try:
            async with AsyncOpenAI(api_key=api_key, timeout=30.0, max_retries=2) as client:
                response = await client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. Use the provided context to answer questions. Cite sources using [1], [2], etc.",
                        },
                        {"role": "user", "content": full_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=500,
                )

            response_text = response.choices[0].message.content or ""
            tokens_input = response.usage.prompt_tokens if response.usage else 0
            tokens_output = response.usage.completion_tokens if response.usage else 0

            # Simple heuristic cost estimation (gpt-3.5-turbo: $0.50 / 1M input, $1.50 / 1M output)
            cost_usd = (tokens_input / 1_000_000 * 0.50) + (tokens_output / 1_000_000 * 1.50)

        except Exception as exc:
            logger.exception("OpenAI generation failed")
            raise RuntimeError("OpenAI generation failed") from exc

        latency_ms = (time.time() - start_time) * 1000

        return {
            "text": response_text,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "model_metadata": {"model": self.model_name, "provider": "openai"},
        }


class LocalDeterministicLLMAdapter(LLMAdapter):
    """
    Local deterministic LLM generator for development and testing
    when external paid provider API keys are not supplied.
    """

    def __init__(self, model_name: str = "local-rag-v1"):
        self.model_name = model_name

    async def generate(self, prompt: str, context: list[RetrievedChunk]) -> dict[str, Any]:
        start_time = time.time()
        if context:
            citations_text = " ".join([f"[{i+1}]" for i in range(min(len(context), 3))])
            snippets = " ".join([c.text_content for c in context[:2]])
            response_text = f"Synthesized answer based on verified context: {snippets} {citations_text}".strip()
        else:
            response_text = f"Synthesized general response for: {prompt[:100]}".strip()

        tokens_input = max(len(prompt.split()) + sum(len(c.text_content.split()) for c in context), 1)
        tokens_output = max(len(response_text.split()), 1)
        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "text": response_text,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "latency_ms": max(latency_ms, 5.0),
            "cost_usd": (tokens_input * 0.000001) + (tokens_output * 0.000002),
            "model_metadata": {"model": self.model_name, "provider": "local-deterministic"},
        }
