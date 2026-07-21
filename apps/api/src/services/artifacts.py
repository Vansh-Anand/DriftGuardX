"""
DriftGuard-X v2 — Content-Addressed Artifact Storage

Provides a storage interface for large payloads (prompts, raw tool outputs).
Currently backed by local filesystem mock.
"""
import hashlib
import json
import os
from abc import ABC, abstractmethod
from typing import Any

# Default storage location for local mock
_STORAGE_DIR = os.environ.get("DGX_ARTIFACT_STORAGE_DIR", "/tmp/dgx_artifacts")


class ArtifactStore(ABC):
    @abstractmethod
    async def put(self, payload: Any) -> str:
        """Store the payload and return its content-addressed hash (e.g. sha256:abcd...)"""
        pass

    @abstractmethod
    async def get(self, artifact_hash: str) -> Any | None:
        """Retrieve the payload by its hash, returning None if not found."""
        pass


class LocalFilesystemArtifactStore(ArtifactStore):
    def __init__(self, base_dir: str = _STORAGE_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _hash_payload(self, serialized: bytes) -> str:
        return "sha256:" + hashlib.sha256(serialized).hexdigest()

    def _serialize(self, payload: Any) -> bytes:
        if isinstance(payload, (dict, list)):
            return json.dumps(payload, sort_keys=True, default=str).encode()
        elif isinstance(payload, str):
            return payload.encode()
        elif isinstance(payload, bytes):
            return payload
        return str(payload).encode()

    async def put(self, payload: Any) -> str:
        serialized = self._serialize(payload)
        artifact_hash = self._hash_payload(serialized)
        
        file_path = os.path.join(self.base_dir, artifact_hash.split(":")[1])
        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(serialized)
                
        return artifact_hash

    async def get(self, artifact_hash: str) -> Any | None:
        if not artifact_hash.startswith("sha256:"):
            return None
            
        file_path = os.path.join(self.base_dir, artifact_hash.split(":")[1])
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, "rb") as f:
            data = f.read()
            
        try:
            return json.loads(data)
        except Exception:
            return data.decode(errors="replace")


# Singleton instance for dependency injection
artifact_store = LocalFilesystemArtifactStore()

async def get_artifact_store() -> ArtifactStore:
    return artifact_store
