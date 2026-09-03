"""Canonical evidence-provenance taxonomy shared by every product surface."""

import enum


class RecoveryEvidenceKind(str, enum.Enum):
    """How recovery evidence was obtained, ordered from weakest to strongest."""

    UNAVAILABLE = "unavailable"
    SYNTHETIC_DEMO = "synthetic_demo"
    SYNTHETIC_SIMULATION = "synthetic_simulation"
    ESTIMATED = "estimated"
    TEST_FIXTURE = "test_fixture"
    CONTROLLED_REPLAY = "controlled_replay"
    PRODUCTION_CANARY = "production_canary"
    REAL_EXECUTION = "real_execution"

    @property
    def is_synthetic(self) -> bool:
        return self in {
            RecoveryEvidenceKind.SYNTHETIC_DEMO,
            RecoveryEvidenceKind.SYNTHETIC_SIMULATION,
            RecoveryEvidenceKind.TEST_FIXTURE
        }
