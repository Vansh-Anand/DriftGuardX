"""Canonical evidence-provenance taxonomy shared by every product surface."""

import enum


class EvidenceClassification(str, enum.Enum):
    """Canonical classification for how evidence was obtained, applied across all artifacts."""

    PRODUCTION = "PRODUCTION"
    REAL_CONTROLLED_EXPERIMENT = "REAL_CONTROLLED_EXPERIMENT"
    SYNTHETIC_SIMULATION = "SYNTHETIC_SIMULATION"
    TEST_FIXTURE = "TEST_FIXTURE"
    UNVERIFIED = "UNVERIFIED"

    @property
    def is_synthetic(self) -> bool:
        return self in {
            EvidenceClassification.SYNTHETIC_SIMULATION,
            EvidenceClassification.TEST_FIXTURE,
        }
