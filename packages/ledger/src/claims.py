"""
DriftGuard-X v2 — Claims Ledger

Tracks which claims are Implemented, Measured, Inferred, Planned, or Rejected.
Never confuses implemented functionality with causal proofs or legal certifications.

PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from packages.contracts.src.models import DiagnosisClaimStatus

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class LedgerEntry:
    """A single claim entry in the ledger."""

    claim_id: str
    title: str
    description: str
    status: DiagnosisClaimStatus
    evidence: list[str] = field(default_factory=list)
    added_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "evidence": self.evidence,
            "added_at": self.added_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
        }


class ClaimsLedger:
    """
    In-memory claims ledger with optional JSON persistence.
    Separates implemented, measured, inferred, planned, and rejected claims.
    """

    def __init__(self) -> None:
        self._entries: dict[str, LedgerEntry] = {}

    def add(
        self,
        claim_id: str,
        title: str,
        description: str,
        status: DiagnosisClaimStatus,
        evidence: list[str] | None = None,
        notes: str = "",
    ) -> LedgerEntry:
        entry = LedgerEntry(
            claim_id=claim_id,
            title=title,
            description=description,
            status=status,
            evidence=evidence or [],
            notes=notes,
        )
        self._entries[claim_id] = entry
        return entry

    def get(self, claim_id: str) -> LedgerEntry | None:
        return self._entries.get(claim_id)

    def update_status(self, claim_id: str, status: DiagnosisClaimStatus, notes: str = "") -> None:
        entry = self._entries.get(claim_id)
        if entry is None:
            raise KeyError(f"Claim '{claim_id}' not found")
        entry.status = status
        entry.updated_at = datetime.now(UTC).isoformat()
        if notes:
            entry.notes = notes

    def list_by_status(self, status: DiagnosisClaimStatus) -> list[LedgerEntry]:
        return [e for e in self._entries.values() if e.status == status]

    def all_entries(self) -> list[LedgerEntry]:
        return list(self._entries.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self._entries.values()],
            "summary": {s.value: len(self.list_by_status(s)) for s in DiagnosisClaimStatus},
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# ─── Prompt 01 Claims ─────────────────────────────────────────────────────────


def build_prompt01_ledger() -> ClaimsLedger:
    """Seed the ledger with Prompt 01 claims."""
    ledger = ClaimsLedger()

    ledger.add(
        "P01-TRACE-01",
        "Versioned span recording",
        "Each pipeline component records an OTEL-compatible span with version ID.",
        DiagnosisClaimStatus.IMPLEMENTED,
        evidence=["apps/api/src/pipeline/mock_rag.py", "packages/trace_sdk/src/tracer.py"],
    )
    ledger.add(
        "P01-TRACE-02",
        "Input/output hashing (no raw prompts stored)",
        "All inputs and outputs are SHA-256 hashed before persistence.",
        DiagnosisClaimStatus.IMPLEMENTED,
        evidence=["packages/trace_sdk/src/tracer.py::hash_payload"],
    )
    ledger.add(
        "P01-REPLAY-01",
        "Deterministic retriever rollback replay",
        "Replay swaps retriever v2→v1 with all other versions frozen.",
        DiagnosisClaimStatus.IMPLEMENTED,
        evidence=["packages/replay/src/engine.py"],
    )
    ledger.add(
        "P01-REPLAY-02",
        "Causal proof of faithfulness improvement",
        "We observe before/after reliability delta but do not claim causal proof.",
        DiagnosisClaimStatus.INFERRED,
        notes="Requires matched counterfactual RCT to establish causality — not implemented in Prompt 01.",
    )
    ledger.add(
        "P01-POLICY-01",
        "Default-deny for high-risk actions",
        "Policy gate denies production mutations, memory deletes, and permission grants.",
        DiagnosisClaimStatus.IMPLEMENTED,
        evidence=["packages/policy/src/gate.py"],
    )
    ledger.add(
        "P01-CERT-01",
        "Cryptographic recovery certificate",
        "Certificate hash computed over run_id, replay_id, intervention_id.",
        DiagnosisClaimStatus.IMPLEMENTED,
        evidence=["packages/contracts/src/models.py::RecoveryCertificate"],
    )
    ledger.add(
        "P01-PATENT-01",
        "Novel causal reliability graph",
        "Causal graph construction not yet implemented — reserved for Prompt 03.",
        DiagnosisClaimStatus.PLANNED,
        notes="Do not claim patent novelty for unimplemented feature.",
    )

    return ledger
