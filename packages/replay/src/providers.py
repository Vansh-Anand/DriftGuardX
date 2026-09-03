"""
DriftGuard-X v2 — Deterministic Providers
PRIVATE — All Rights Reserved.
"""

import hashlib
from typing import Any

from packages.contracts.src.models import ComponentVersion
from packages.replay.src.engine import ComponentExecutor


class DeterministicEmbedder(ComponentExecutor):
    def execute(
        self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42
    ) -> dict[str, Any]:
        text = inputs.get("text", "")
        # Deterministic pseudo-embedding based on hash of text and seed
        h = hashlib.sha256(f"{text}:{seed}:{version.id}".encode()).hexdigest()
        vector = [int(h[i : i + 2], 16) / 255.0 for i in range(0, 32, 2)]
        return {"embedding": vector}


class DeterministicRetriever(ComponentExecutor):
    def execute(
        self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42
    ) -> dict[str, Any]:
        query = inputs.get("query", "")
        # A mock returning stable docs
        return {
            "documents": [
                {
                    "id": f"doc-{seed}-1",
                    "text": f"Found deterministic match 1 for: {query}",
                    "score": 0.9,
                },
                {
                    "id": f"doc-{seed}-2",
                    "text": f"Found deterministic match 2 for: {query}",
                    "score": 0.8,
                },
            ]
        }


class DeterministicGenerator(ComponentExecutor):
    def execute(
        self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42
    ) -> dict[str, Any]:
        prompt = inputs.get("prompt", "")
        return {
            "response": f"[Seed {seed}] Deterministic generation based on: {prompt[:20]}...",
            "tokens_used": 15,
        }


class DeterministicTool(ComponentExecutor):
    def execute(
        self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42
    ) -> dict[str, Any]:
        tool_name = inputs.get("tool_name", "unknown")
        args = inputs.get("args", {})
        return {"tool_result": f"Tool {tool_name} executed deterministically with args {args}"}


class OptionalRealProviderWrapper(ComponentExecutor):
    """
    Wraps a real provider (e.g., OpenAI API) with forced seeds, while
    marking the execution as non-deterministic in the trace.
    """

    def __init__(self, real_executor: ComponentExecutor):
        self.real = real_executor

    def execute(
        self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42
    ) -> dict[str, Any]:
        inputs["_force_seed"] = seed
        result = self.real.execute(inputs, version=version, seed=seed)
        result["_warning"] = "NON_DETERMINISTIC_PROVIDER_USED"
        return result
