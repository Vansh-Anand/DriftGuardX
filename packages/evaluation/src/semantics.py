import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


class SemanticModelUnavailableError(Exception):
    pass

@dataclass
class SemanticDecision:
    decision: bool
    drift_score: float
    diagnostics: dict[str, Any]

class SemanticEncoder(Protocol):
    def encode(self, text: str) -> np.ndarray:
        ...

class DeterministicFakeEncoder:
    """
    TEST ONLY. Derives a 'semantic' embedding deterministically from SHA-256 hash bytes.
    DO NOT use in production.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def encode(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode('utf-8')).digest()
        # Expand hash to desired dimension by tiling
        arr = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
        arr = arr / 255.0  # normalize to 0-1
        tiled = np.tile(arr, int(np.ceil(self.dimension / len(arr))))[:self.dimension]
        # L2 normalize
        norm = np.linalg.norm(tiled)
        if norm > 0:
            return tiled / norm
        return tiled

class SentenceTransformerEncoder:
    """
    REAL implementation using a local SentenceTransformer model.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_identifier = f"sentence-transformers/{model_name}"
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
        except ImportError:
            raise SemanticModelUnavailableError(
                "SentenceTransformer requires 'sentence-transformers' package. "
                "Install via `pip install sentence-transformers`."
            )

    def encode(self, text: str) -> np.ndarray:
        # Normalize input
        text = text.strip()
        if not text:
            return np.zeros(384, dtype=np.float32) # Default dimension for MiniLM

        emb = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return emb[0]


class CosineDriftComparator:
    def __init__(self, encoder: SemanticEncoder, threshold: float = 0.85):
        self.encoder = encoder
        self.threshold = threshold

    def compare(self, baseline: str, observation: str) -> SemanticDecision:
        b_emb = self.encoder.encode(baseline)
        o_emb = self.encoder.encode(observation)

        # Calculate cosine similarity
        similarity = float(np.dot(b_emb, o_emb))
        drift_score = 1.0 - similarity

        is_drifted = similarity < self.threshold

        return SemanticDecision(
            decision=is_drifted,
            drift_score=drift_score,
            diagnostics={"similarity": similarity, "threshold": self.threshold}
        )

def get_semantic_encoder(force_real: bool = False) -> SemanticEncoder:
    """
    Returns an appropriate encoder based on DGX_MODE.
    """
    from apps.api.src.config import RuntimeSecurityConfig
    config = RuntimeSecurityConfig.load()
    if force_real or not config.allow_fake_encoders:
        return SentenceTransformerEncoder()
    return DeterministicFakeEncoder()
