import pytest
import os
import time
from unittest.mock import patch, MagicMock, AsyncMock

from packages.rag_pipeline.src.providers import ProviderRegistry, LocalDeterministicProvider, OpenAIProvider
from packages.rationale.src.llm import invoke_llm

@pytest.mark.asyncio
async def test_local_deterministic_provider():
    provider = LocalDeterministicProvider()
    response = await provider.generate(prompt="Hello", context=["World"], temperature=0.5, max_tokens=100)
    
    assert response.text == "Reasoning produced."
    assert response.metadata["provider_id"] == "local-deterministic"
    assert response.metadata["model_id"] == "default-model"
    assert response.metadata["temperature"] == 0.5
    assert response.metadata["max_tokens"] == 100
    assert "latency_ms" in response.metadata
    assert response.metadata["token_counts"]["prompt"] == 1
    assert response.metadata["token_counts"]["completion"] == 2

@pytest.mark.asyncio
async def test_openai_provider_success():
    provider = OpenAIProvider()
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mocked OpenAI response"))]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    mock_response.id = "req-123"
    
    with patch("openai.AsyncClient") as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
        
        response = await provider.generate(prompt="Hello", context=["World"], temperature=0.7)
        
        assert response.text == "Mocked OpenAI response"
        assert response.metadata["provider_id"] == "openai"
        assert response.metadata["model_id"] == "gpt-4o"
        assert response.metadata["temperature"] == 0.7
        assert response.metadata["request_id"] == "req-123"
        assert response.metadata["token_counts"]["prompt"] == 10
        assert response.metadata["token_counts"]["completion"] == 20
        # (10 * 0.005 + 20 * 0.015) / 1000 = (0.05 + 0.3) / 1000 = 0.00035
        assert response.metadata["cost_usd"] == 0.00035

def test_provider_registry():
    registry = ProviderRegistry()
    assert isinstance(registry.get_provider("local-deterministic"), LocalDeterministicProvider)
    assert isinstance(registry.get_provider("openai"), OpenAIProvider)
    
    with pytest.raises(ValueError):
        registry.get_provider("unknown")

def test_invoke_llm_real_mode_no_key():
    with patch.dict(os.environ, {"DGX_REAL_MODE": "1", "OPENAI_API_KEY": ""}):
        with pytest.raises(RuntimeError, match="real_mode is enabled but OPENAI_API_KEY is not set."):
            invoke_llm("prompt", "{}")

def test_invoke_llm_real_mode_with_key():
    with patch.dict(os.environ, {"DGX_REAL_MODE": "1", "OPENAI_API_KEY": "fake_key"}):
        with patch("packages.rag_pipeline.src.providers.OpenAIProvider.generate") as mock_gen:
            import asyncio
            mock_gen.return_value = MagicMock(text="Real response", metadata={"latency_ms": 42.0})
            
            # Since invoke_llm calls generate via asyncio, we need to handle it.
            # invoke_llm will run it in a new loop or thread pool.
            # We mock asyncio.run for simplicity here to return the ProviderResponse directly.
            with patch("asyncio.run", return_value=mock_gen.return_value):
                content, latency = invoke_llm("prompt", "{}")
                
                assert content == "Real response"
                assert latency == 42.0

def test_invoke_llm_dev_mode():
    with patch.dict(os.environ, {"DGX_REAL_MODE": "0", "DGX_USE_REAL_LLM": "0"}):
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = MagicMock(text="Local response", metadata={"latency_ms": 10.0})
            
            evidence = '{"ranked_cause_component": "A", "original_version_tag": "v1", "replay_version_tag": "v2"}'
            content, latency = invoke_llm("prompt", evidence)
            
            assert "Mock generated text" in content
            assert isinstance(latency, float)
            assert latency >= 0.0
