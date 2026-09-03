"""
DriftGuard-X v2 — Provider Registry
PRIVATE — All Rights Reserved.

Registry for resolving LLM models to provider credentials, handling failovers,
and tracking capacity/costs. Keep secrets out of code and database logs.
"""

import os
from typing import Any


class ProviderStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class ModelConfig:
    def __init__(self, provider: str, model_id: str, cost_per_1k_tokens: float):
        self.provider = provider
        self.model_id = model_id
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.status = ProviderStatus.HEALTHY


# ─── Static Mock Registry ─────────────────────────────────────────────────────

# In a full deployment, these could be loaded from an external KMS or secure vault.
_REGISTRY = {
    "gpt-4o": ModelConfig("openai", "gpt-4o", 0.005),
    "claude-3-opus": ModelConfig("anthropic", "claude-3-opus-20240229", 0.015),
    "mock-local": ModelConfig("local", "mock-model-v1", 0.0),
}


class ProviderRegistry:

    @staticmethod
    def get_model_config(model_name: str) -> ModelConfig | None:
        """Look up configuration and pricing for a model."""
        return _REGISTRY.get(model_name)

    @staticmethod
    def get_api_key(provider: str) -> str | None:
        """
        Securely retrieve API keys from environment/vault.
        Never log or return this in an API response.
        """
        if provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        if provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        return None

    @staticmethod
    def list_providers() -> dict[str, Any]:
        """List provider capabilities and health (no secrets)."""
        return {
            name: {
                "provider": config.provider,
                "status": config.status,
                "cost_per_1k": config.cost_per_1k_tokens,
            }
            for name, config in _REGISTRY.items()
        }
