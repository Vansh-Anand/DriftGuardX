import os
import logging
from typing import Dict, Any

try:
    from ragas import evaluate
    from ragas.metrics import answer_correctness, faithfulness, context_precision
    from datasets import Dataset
    HAS_RAGAS = True
except ImportError:
    HAS_RAGAS = False

logger = logging.getLogger(__name__)

class RagasEvaluator:
    def __init__(self):
        self.enabled = HAS_RAGAS and bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))
        if not self.enabled:
            logger.warning("Ragas evaluation is disabled. Missing 'ragas' package or 'LLM_API_KEY'.")

    def evaluate_episode(self, query: str, expected_answer: str, generated_answer: str, retrieved_contexts: list[str]) -> Dict[str, float]:
        if not self.enabled:
            # Fallback to deterministic string distance if ragas is unavailable
            return {
                "answer_correctness": 1.0 if expected_answer and expected_answer.lower() in generated_answer.lower() else 0.0,
                "faithfulness": 0.0,  # Cannot compute deterministically
                "context_precision": 0.0, # Cannot compute deterministically
                "used_llm": 0.0
            }
            
        data = {
            "question": [query],
            "answer": [generated_answer],
            "contexts": [retrieved_contexts],
            "ground_truth": [expected_answer]
        }
        dataset = Dataset.from_dict(data)
        
        try:
            result = evaluate(
                dataset,
                metrics=[answer_correctness, faithfulness, context_precision]
            )
            return {
                "answer_correctness": result.get("answer_correctness", 0.0),
                "faithfulness": result.get("faithfulness", 0.0),
                "context_precision": result.get("context_precision", 0.0),
                "used_llm": 1.0
            }
        except Exception as e:
            logger.error(f"Ragas evaluation failed: {e}")
            return {
                "answer_correctness": 0.0,
                "faithfulness": 0.0,
                "context_precision": 0.0,
                "used_llm": 0.0
            }
