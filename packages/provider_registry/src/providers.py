from abc import ABC, abstractmethod
from typing import Any

class BaseProvider(ABC):
    def __init__(self, model_id: str, cost_per_1k_tokens: float):
        self.model_id = model_id
        self.cost_per_1k_tokens = cost_per_1k_tokens

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """
        Generate a response given a prompt.
        Should return a dictionary containing at least:
        - "text": The generated text string
        - "token_usage": A dict with input/output token counts
        - "provider_metadata": Any specific trace IDs or model versions used.
        """
        pass

class MockProvider(BaseProvider):
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "text": f"MOCK_RESPONSE for: {prompt[:20]}...",
            "token_usage": {"input": len(prompt) // 4, "output": 10},
            "provider_metadata": {"model": self.model_id, "mock": True}
        }

class OpenAIProvider(BaseProvider):
    def __init__(self, model_id: str, cost_per_1k_tokens: float, api_key: str | None = None):
        super().__init__(model_id, cost_per_1k_tokens)
        self.api_key = api_key
        
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        # In a real app we would use openai client here.
        # This is a stub for the abstraction contract.
        return {
            "text": "OpenAI generated text",
            "token_usage": {"input": 10, "output": 20},
            "provider_metadata": {"model": self.model_id, "temperature": kwargs.get("temperature", 0.7)}
        }

class AnthropicProvider(BaseProvider):
    def __init__(self, model_id: str, cost_per_1k_tokens: float, api_key: str | None = None):
        super().__init__(model_id, cost_per_1k_tokens)
        self.api_key = api_key
        
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")
        return {
            "text": "Anthropic generated text",
            "token_usage": {"input": 10, "output": 20},
            "provider_metadata": {"model": self.model_id}
        }
