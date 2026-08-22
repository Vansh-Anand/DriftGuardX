from typing import List, Dict, Any
import time
from packages.rag_pipeline.src.interfaces import LLMAdapter, RetrievedChunk
from apps.api.src.config import settings

class SafeLLMAdapter(LLMAdapter):
    """
    LLM Adapter that requires explicit configuration and API key.
    Enforces the 'Do not call external LLM APIs until I explicitly provide an API key' rule.
    """
    def __init__(self, model_name: str = "gpt-4-turbo-preview"):
        self.model_name = model_name
        
    async def generate(self, prompt: str, context: List[RetrievedChunk]) -> Dict[str, Any]:
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        
        if not api_key:
            raise RuntimeError("LLM API Key missing or unapproved. Cannot call external LLM provider.")
            
        # Context building
        context_str = "\n\n".join([f"[{i+1}] {c.text_content}" for i, c in enumerate(context)])
        full_prompt = f"{prompt}\n\nContext:\n{context_str}"
        
        # We would use httpx or openai client here
        # For now, if we get an API key, we simulate a response or use a basic client
        # To truly integrate, one might use liteLLM or direct HTTP calls
        
        start_time = time.time()
        
        # Simulating external call since we don't have the key yet
        response_text = "This is a response generated based on the provided context."
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "text": response_text,
            "tokens_input": len(full_prompt) // 4,  # Rough estimate
            "tokens_output": len(response_text) // 4,
            "latency_ms": latency_ms,
            "cost_usd": 0.001,
            "model_metadata": {
                "model": self.model_name,
                "provider": "simulated"
            }
        }
