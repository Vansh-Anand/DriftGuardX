"""
DriftGuard-X v2 — Diffusion Inference Caching
"""
import hashlib
import json
from typing import Dict, Any, Optional

class DiffusionCache:
    """
    In-memory mock of a Redis/Memcached inference cache for diffusion steps.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        
    def _compute_key(self, graph_json: str, detector_version: str, model_version: str) -> str:
        h = hashlib.sha256()
        h.update(graph_json.encode('utf-8'))
        h.update(detector_version.encode('utf-8'))
        h.update(model_version.encode('utf-8'))
        return h.hexdigest()

    def get(self, graph_json: str, detector_version: str, model_version: str) -> Optional[Dict[str, Any]]:
        key = self._compute_key(graph_json, detector_version, model_version)
        return self._cache.get(key)
        
    def set(self, graph_json: str, detector_version: str, model_version: str, result: Dict[str, Any]):
        key = self._compute_key(graph_json, detector_version, model_version)
        self._cache[key] = result
        
    def clear(self):
        self._cache.clear()
