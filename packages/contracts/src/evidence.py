"""Canonical evidence-provenance taxonomy shared by every product surface."""

import enum


class RecoveryEvidenceKind(str, enum.Enum):
    """How recovery evidence was obtained, ordered from weakest to strongest."""

    SYNTHETIC_SIMULATION = "synthetic_simulation"
    CONTROLLED_REPLAY = "controlled_replay"
    PRODUCTION_CANARY = "production_canary"

    @property
    def is_synthetic(self) -> bool:
        return self is RecoveryEvidenceKind.SYNTHETIC_SIMULATION
