"""
DriftGuard-X v2 — Coverage Monitor
PRIVATE — All Rights Reserved.

Monitors calibration freshness in production-like streams and downgrades
outstanding certificates when calibration has expired or drifted.

In a production deployment this module would subscribe to a Kafka / Pub-Sub
topic of new diagnosis events.  For the prototype it operates on an in-memory
list of events and a CalibrationDataset.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from packages.evaluation.src.calibration import (
    CalibrationDataset,
    CoverageReport,
    measure_coverage,
    NOMINAL_LEVELS,
    MAX_UNDERCOVERAGE_GAP,
    MIN_CAL_EPISODES,
)


# ─── Events ───────────────────────────────────────────────────────────────────

@dataclass
class DiagnosisEvent:
    """Represents a completed diagnosis arriving in the production stream."""
    run_id: str
    certificate_status: str    # CERTIFIED | UNCERTIFIED | REJECTED at issue time
    issued_at: datetime


@dataclass
class DowngradeEvent:
    """Emitted when a previously CERTIFIED diagnosis has its cert downgraded."""
    run_id: str
    original_status: str
    new_status: str
    reason: str
    downgraded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Monitor ──────────────────────────────────────────────────────────────────

class CoverageMonitor:
    """
    Checks calibration freshness and coverage on each incoming diagnosis event.
    Issues DowngradeEvents for any CERTIFIED diagnoses whose calibration has
    since expired or drifted below acceptable coverage.
    """

    def __init__(
        self,
        dataset: CalibrationDataset,
        max_calibration_age_days: int = 30,
        check_interval_events: int = 50,  # re-measure coverage every N events
    ):
        self._dataset = dataset
        self._max_age_days = max_calibration_age_days
        self._check_interval = check_interval_events
        self._event_count = 0
        self._last_coverage_report: CoverageReport | None = None
        self._downgrade_log: List[DowngradeEvent] = []

    def _calibration_expired(self) -> bool:
        """True if the newest calibration episode is older than max_calibration_age_days."""
        episodes = self._dataset.episodes()
        if not episodes:
            return True
        latest = max(ep.recorded_at for ep in episodes)
        age = (datetime.now(timezone.utc) - latest).total_seconds() / 86400
        return age > self._max_age_days

    def _coverage_drifted(self) -> bool:
        """True if any nominal level shows undercoverage beyond the allowed gap."""
        if self._last_coverage_report is None:
            return False
        for level, obs in self._last_coverage_report.coverage_by_level.items():
            if (level - obs) > MAX_UNDERCOVERAGE_GAP:
                return True
        return False

    def process_event(self, event: DiagnosisEvent) -> List[DowngradeEvent]:
        """
        Process one incoming diagnosis event.
        Returns a (possibly empty) list of DowngradeEvents.
        """
        self._event_count += 1
        downgrades: List[DowngradeEvent] = []

        # Re-measure coverage periodically
        if self._event_count % self._check_interval == 0:
            if len(self._dataset) >= MIN_CAL_EPISODES:
                self._last_coverage_report = measure_coverage(self._dataset)

        # Only CERTIFIED diagnoses can be downgraded
        if event.certificate_status != "CERTIFIED":
            return []

        reasons = []
        if self._calibration_expired():
            reasons.append(
                f"Calibration expired (newest episode older than {self._max_age_days} days)."
            )
        if self._coverage_drifted():
            reasons.append("Coverage drift detected beyond allowed undercoverage gap.")

        if reasons:
            dg = DowngradeEvent(
                run_id=event.run_id,
                original_status="CERTIFIED",
                new_status="UNCERTIFIED",
                reason=" | ".join(reasons),
            )
            self._downgrade_log.append(dg)
            downgrades.append(dg)

        return downgrades

    def downgrade_log(self) -> List[DowngradeEvent]:
        return list(self._downgrade_log)

    def latest_coverage_report(self) -> CoverageReport | None:
        return self._last_coverage_report
