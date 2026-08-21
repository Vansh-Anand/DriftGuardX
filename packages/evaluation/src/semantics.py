from typing import Protocol, List, Dict, Any, Optional
import math
from pydantic import BaseModel, Field

class DriftDecision(BaseModel):
    drift_score: float
    threshold: float
    model_version: str
    decision: bool  # True if drifted (score >= threshold)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class SemanticEncoder(Protocol):
    def encode(self, text: str) -> List[float]:
        """Encodes text into a numeric vector."""
        ...
        
    @property
    def model_identifier(self) -> str:
        """Returns a string identifying the encoding model."""
        ...


class SemanticDriftComparator(Protocol):
    def compare(self, reference: str, candidate: str, threshold: float = 0.2) -> DriftDecision:
        """
        Compares reference text against candidate text.
        Returns a DriftDecision.
        """
        ...


class DeterministicFakeEncoder:
    """A fake encoder for testing that hashes text into a fixed-size vector."""
    def __init__(self, dimensions: int = 16):
        self.dimensions = dimensions
        
    def encode(self, text: str) -> List[float]:
        # Simple deterministic hashing to a vector
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).digest()
        # map bytes to floats [-1, 1]
        vector = []
        for i in range(self.dimensions):
            byte_val = h[i % len(h)]
            vector.append((byte_val / 127.5) - 1.0)
            
        # Normalize
        magnitude = math.sqrt(sum(x*x for x in vector))
        if magnitude == 0:
            return [0.0] * self.dimensions
        return [x / magnitude for x in vector]

    @property
    def model_identifier(self) -> str:
        return "DeterministicFakeEncoder-v1"


class CosineDriftComparator:
    """Compares semantic drift using cosine similarity of encodings."""
    
    def __init__(self, encoder: SemanticEncoder):
        self.encoder = encoder
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)

    def compare(self, reference: str, candidate: str, threshold: float = 0.2) -> DriftDecision:
        vec_ref = self.encoder.encode(reference)
        vec_cand = self.encoder.encode(candidate)
        
        sim = self._cosine_similarity(vec_ref, vec_cand)
        # Drift score is distance from perfect similarity
        drift_score = 1.0 - sim
        
        is_drifted = drift_score > threshold
        
        return DriftDecision(
            drift_score=drift_score,
            threshold=threshold,
            model_version=self.encoder.model_identifier,
            decision=is_drifted,
            diagnostics={
                "cosine_similarity": sim,
                "reference_length": len(reference),
                "candidate_length": len(candidate)
            }
        )
