"""
DriftGuard-X v2 — Core Drift Detector Interfaces
"""
from typing import Any, Protocol

from packages.contracts.src.models import DetectorOutput, DetectorThreshold


class DriftDetector(Protocol):
    """Base interface for all drift detectors."""

    @property
    def detector_name(self) -> str:
        ...

    def evaluate(
        self,
        trace_or_span: Any,
        thresholds: dict[str, DetectorThreshold] | None = None,
        **kwargs: Any
    ) -> list[DetectorOutput]:
        """Evaluate a trace or span and produce detector outputs using calibrated thresholds."""
        ...
