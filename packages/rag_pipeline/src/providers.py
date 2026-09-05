"""
DriftGuard-X v2 — Provider Abstraction
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: list[str], **kwargs: Any) -> ProviderResponse:
        pass


class LocalDeterministicProvider(BaseProvider):
    async def generate(self, prompt: str, context: list[str], **kwargs: Any) -> ProviderResponse:
        start_time = time.monotonic()
        text = "Reasoning produced."
        latency_ms = (time.monotonic() - start_time) * 1000
        
        return ProviderResponse(
            text=text,
            metadata={
                "provider_id": "local-deterministic",
                "model_id": "default-model",
                "temperature": kwargs.get("temperature", 0.0),
                "max_tokens": kwargs.get("max_tokens", None),
                "request_id": str(uuid.uuid4()),
                "latency_ms": latency_ms,
                "token_counts": {"prompt": len(prompt.split()), "completion": len(text.split())},
                "cost_usd": 0.0,
            },
        )


class OpenAIProvider(BaseProvider):
    async def generate(self, prompt: str, context: list[str], **kwargs: Any) -> ProviderResponse:
        start_time = time.monotonic()
        import openai
        
        client = openai.AsyncClient()
        model = kwargs.get("model", "gpt-4o")
        messages = [{"role": "system", "content": prompt}]
        if context:
            messages.append({"role": "user", "content": "\n".join(context)})
            
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens"),
            )
            text = response.choices[0].message.content or ""
            latency_ms = (time.monotonic() - start_time) * 1000
            
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            # Simple cost heuristic for gpt-4o
            cost_usd = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000.0
            
            return ProviderResponse(
                text=text,
                metadata={
                    "provider_id": "openai",
                    "model_id": model,
                    "temperature": kwargs.get("temperature", 0.0),
                    "max_tokens": kwargs.get("max_tokens", None),
                    "request_id": response.id,
                    "latency_ms": latency_ms,
                    "token_counts": {"prompt": prompt_tokens, "completion": completion_tokens},
                    "cost_usd": cost_usd,
                },
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProviderResponse(
                text="",
                metadata={
                    "provider_id": "openai",
                    "model_id": model,
                    "error": str(e),
                    "latency_ms": latency_ms,
                }
            )


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseProvider] = {
            "local-deterministic": LocalDeterministicProvider(),
            "openai": OpenAIProvider(),
        }
        
    def get_provider(self, provider_id: str) -> BaseProvider:
        if provider_id not in self._providers:
            raise ValueError(f"Provider '{provider_id}' not found in registry.")
        return self._providers[provider_id]
        
    def register_provider(self, provider_id: str, provider: BaseProvider) -> None:
        self._providers[provider_id] = provider
