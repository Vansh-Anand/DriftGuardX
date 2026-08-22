import os
from typing import Protocol, List, Dict, Any, Optional
from dataclasses import dataclass

class EntailmentUnavailableError(Exception):
    pass

@dataclass
class EntailmentDecision:
    claim: str
    classification: str # SUPPORTED, CONTRADICTED, UNSUPPORTED, UNKNOWN
    confidence: float
    supporting_source_ids: List[str]
    provider_version: str

class EntailmentProvider(Protocol):
    def check_entailment(self, premise: str, hypothesis: str, source_id: str) -> EntailmentDecision:
        ...

class FakeEntailmentProvider:
    """
    TEST ONLY. Uses simple lexical overlap.
    DO NOT use in production.
    """
    def check_entailment(self, premise: str, hypothesis: str, source_id: str) -> EntailmentDecision:
        p_words = set(premise.lower().split())
        h_words = set(hypothesis.lower().split())
        overlap = len(p_words.intersection(h_words)) / max(1, len(h_words))
        
        if overlap > 0.5:
            c = "SUPPORTED"
        elif overlap < 0.1:
            c = "CONTRADICTED"
        else:
            c = "UNSUPPORTED"
            
        return EntailmentDecision(
            claim=hypothesis,
            classification=c,
            confidence=overlap,
            supporting_source_ids=[source_id] if c == "SUPPORTED" else [],
            provider_version="fake-lexical-v1"
        )

class SentenceTransformerNLIProvider:
    """
    REAL NLI implementation using a cross-encoder model.
    """
    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small"):
        self.provider_version = f"sentence-transformers/{model_name}"
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_name)
        except ImportError:
            raise EntailmentUnavailableError(
                "NLIProvider requires 'sentence-transformers'. Install via `pip install sentence-transformers`."
            )

    def check_entailment(self, premise: str, hypothesis: str, source_id: str) -> EntailmentDecision:
        try:
            # Model returns logits for [contradiction, entailment, neutral]
            scores = self.model.predict([(premise, hypothesis)])[0]
            label_mapping = ["CONTRADICTED", "SUPPORTED", "UNSUPPORTED"]
            best_idx = scores.argmax()
            classification = label_mapping[best_idx]
            
            # Simple softmax for confidence
            import numpy as np
            exp_scores = np.exp(scores - np.max(scores))
            probs = exp_scores / exp_scores.sum()
            confidence = float(probs[best_idx])
            
            return EntailmentDecision(
                claim=hypothesis,
                classification=classification,
                confidence=confidence,
                supporting_source_ids=[source_id] if classification == "SUPPORTED" else [],
                provider_version=self.provider_version
            )
        except Exception:
            return EntailmentDecision(
                claim=hypothesis,
                classification="UNKNOWN",
                confidence=0.0,
                supporting_source_ids=[],
                provider_version=self.provider_version
            )

def get_entailment_provider(force_real: bool = False) -> EntailmentProvider:
    """
    Returns an appropriate NLI provider based on DGX_MODE.
    """
    mode = os.environ.get("DGX_MODE", "development")
    if mode == "production" or force_real:
        return SentenceTransformerNLIProvider()
    return FakeEntailmentProvider()
