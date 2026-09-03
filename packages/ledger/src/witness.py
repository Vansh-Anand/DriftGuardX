"""
DriftGuard-X v2 — Witnessed Recovery Certificate
Update 4: Commits certificates to an independent transparency log.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.contracts.src.models import RecoveryCertificate
from packages.ledger.src.store import SQLiteTransparencyStore, TransparencyStore


@dataclass
class WitnessCommitResult:
    certificate_commit_hash: str
    ledger_entry_hash: str


class TransparencyWitness:
    """
    Periodically commits certificate Merkle roots to an independent
    witness or transparency log using a TransparencyStore.
    """

    def __init__(self, store: TransparencyStore | None = None):
        # Default to SQLite store if none provided
        self.store = store if store is not None else SQLiteTransparencyStore()

    def _compute_merkle_root(self, hashes: list[str]) -> str:
        if not hashes:
            return ""
        if len(hashes) == 1:
            # Domain separation for leaf node
            return hashlib.sha256(b"\x00" + hashes[0].encode()).hexdigest()

        new_level = []
        for i in range(0, len(hashes), 2):
            left = hashes[i]
            right = hashes[i + 1] if i + 1 < len(hashes) else left
            # Domain separation for internal node
            combined = hashlib.sha256(b"\x01" + left.encode() + right.encode()).hexdigest()
            new_level.append(combined)

        return self._compute_merkle_root(new_level)

    def commit_certificates(
        self,
        certificates: list[RecoveryCertificate],
        policy_snapshot_hash: str,
        canary_result: bool,
    ) -> WitnessCommitResult:
        """
        Commits a batch of certificates and binds the policy snapshot and canary results.
        Returns the WitnessCommitResult containing both the commit hash and the ledger entry hash.
        """
        cert_hashes = [cert.certificate_hash for cert in certificates if cert.is_valid]
        root = self._compute_merkle_root(cert_hashes)

        # Bind the policy and canary result into the final commit hash
        commit_payload = f"{root}:{policy_snapshot_hash}:{canary_result}"
        commit_hash = hashlib.sha256(commit_payload.encode()).hexdigest()

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "commit_hash": commit_hash,
            "merkle_root": root,
            "certificate_count": len(cert_hashes),
            "policy_snapshot": policy_snapshot_hash,
            "canary_passed": canary_result,
        }

        append_result = self.store.append(entry)

        return WitnessCommitResult(
            certificate_commit_hash=commit_hash, ledger_entry_hash=append_result.entry_hash
        )

    def verify_ledger_entry(self, entry_hash: str) -> bool:
        """
        Check if an entry exists and the chain behind it has not been tampered with.
        """
        return self.store.verify_chain(entry_hash)

    def verify_certificate_commit(self, commit_hash: str) -> bool:
        """
        Verify that a certificate commit is recorded in the ledger and the chain is intact.
        """
        for entry in self.store.iterate():
            if entry["payload"].get("commit_hash") == commit_hash:
                return self.store.verify_chain(entry["entry_hash"])
        return False

    def verify_full_chain(self) -> bool:
        """
        Verifies the full integrity of the transparency ledger.
        """
        return self.store.verify_full_chain()
