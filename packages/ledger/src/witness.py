"""
DriftGuard-X v2 — Witnessed Recovery Certificate
Update 4: Commits certificates to an independent transparency log.
"""
import hashlib
import json
import os
from typing import List, Dict, Any
from datetime import datetime, timezone

from packages.contracts.src.models import RecoveryCertificate
from packages.ledger.src.store import TransparencyStore, SQLiteTransparencyStore

class TransparencyWitness:
    """
    Periodically commits certificate Merkle roots to an independent 
    witness or transparency log using a TransparencyStore.
    """
    def __init__(self, store: TransparencyStore | None = None):
        # Default to SQLite store if none provided
        self.store = store if store is not None else SQLiteTransparencyStore()
        
    def _compute_merkle_root(self, hashes: List[str]) -> str:
        if not hashes:
            return ""
        if len(hashes) == 1:
            # Domain separation for leaf node
            return hashlib.sha256((b"\x00" + hashes[0].encode())).hexdigest()
            
        new_level = []
        for i in range(0, len(hashes), 2):
            left = hashes[i]
            right = hashes[i+1] if i+1 < len(hashes) else left
            # Domain separation for internal node
            combined = hashlib.sha256(b"\x01" + left.encode() + right.encode()).hexdigest()
            new_level.append(combined)
            
        return self._compute_merkle_root(new_level)

    def commit_certificates(self, certificates: List[RecoveryCertificate], policy_snapshot_hash: str, canary_result: bool) -> str:
        """
        Commits a batch of certificates and binds the policy snapshot and canary results.
        Returns the root hash of the commit.
        """
        cert_hashes = [cert.certificate_hash for cert in certificates if cert.is_valid]
        root = self._compute_merkle_root(cert_hashes)
        
        # Bind the policy and canary result into the final commit hash
        commit_payload = f"{root}:{policy_snapshot_hash}:{canary_result}"
        commit_hash = hashlib.sha256(commit_payload.encode()).hexdigest()
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit_hash": commit_hash,
            "merkle_root": root,
            "certificate_count": len(cert_hashes),
            "policy_snapshot": policy_snapshot_hash,
            "canary_passed": canary_result
        }
        
        self.store.append(entry)
        
        return commit_hash
        
    def verify_commit(self, commit_hash: str) -> bool:
        """
        Check if a commit exists and has not been tampered with.
        """
        return self.store.verify_chain(commit_hash)
