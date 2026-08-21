"""
DriftGuard-X v2 — Provenance Memory Store
PRIVATE — All Rights Reserved.

Central memory store mapping provenance partitions to memory entries.
Enforces partition quarantine securely before any read operation.
"""
from typing import Any, Dict, List, Optional
import threading

from packages.policy.src.hooks import pre_memory_read_check


class ProvenanceMemoryStore:
    """
    Thread-safe in-memory store for provenance-backed memory.
    Enforces quarantine boundaries using the central policy hook.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._partitions: Dict[str, List[Dict[str, Any]]] = {}
        self._active_quarantines: set[str] = set()

    def write(self, partition_id: str, data: Dict[str, Any], tenant_id: str) -> None:
        """Write data to a partition. Fails if quarantined."""
        with self._lock:
            # Check quarantine before allowing write
            pre_memory_read_check(partition_id, list(self._active_quarantines))
            
            # Enforce cross-tenant isolation
            if not partition_id.startswith(f"{tenant_id}_"):
                raise PermissionError(f"Cross-tenant write violation: tenant {tenant_id} cannot write to partition {partition_id}")
                
            if partition_id not in self._partitions:
                self._partitions[partition_id] = []
            self._partitions[partition_id].append(data)

    def read(self, partition_id: str, tenant_id: str, requester_role: str = "agent") -> List[Dict[str, Any]]:
        """Read data from a partition. Enforces quarantine and tenant isolation."""
        with self._lock:
            # Enforce cross-tenant isolation
            if not partition_id.startswith(f"{tenant_id}_"):
                raise PermissionError(f"Cross-tenant read violation: tenant {tenant_id} cannot read from partition {partition_id}")
                
            # THIS IS THE CRITICAL ENFORCEMENT BOUNDARY
            pre_memory_read_check(
                partition_id,
                list(self._active_quarantines),
                requester_role=requester_role
            )
            return list(self._partitions.get(partition_id, []))

    def quarantine_partition(self, partition_id: str) -> None:
        """
        Quarantine a partition.
        Immediately restricts access and drops it from the readable cache if any existed.
        """
        with self._lock:
            self._active_quarantines.add(partition_id)

    def unquarantine_partition(self, partition_id: str) -> None:
        """Restore access to a quarantined partition."""
        with self._lock:
            self._active_quarantines.discard(partition_id)

    def clear(self) -> None:
        """Clear the store (for testing)."""
        with self._lock:
            self._partitions.clear()
            self._active_quarantines.clear()

# Global instance for the Mock RAG pipeline to use
global_provenance_store = ProvenanceMemoryStore()
