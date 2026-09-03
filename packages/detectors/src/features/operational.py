"""
DriftGuard-X v2 — Operational Drift Detectors
"""

from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class OperationalDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "operational_drift_detector"

    def evaluate(
        self, trace_or_span: Any, thresholds: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[DetectorOutput]:
        from packages.detectors.src.baselines import check_threshold

        thresholds = thresholds or {}
        outputs = []

        def _check(feature: str, val: float, default_t: float, default_op: str) -> bool:
            t = thresholds.get(feature)
            if t:
                return check_threshold(val, t.threshold_value, t.operator)
            return check_threshold(val, default_t, default_op)

        latency = kwargs.get("latency_ms", 100.0)
        latency_threshold = kwargs.get("latency_ms_threshold", 5000.0)
        is_anom = _check("latency", latency, latency_threshold, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="latency",
                value=latency,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
                evidence={"latency_ms": latency},
            )
        )

        token_use = kwargs.get("token_use", 0)
        token_threshold = kwargs.get("token_use_threshold", 4096)
        is_anom = _check("token_use", float(token_use), token_threshold, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="token_use",
                value=float(token_use),
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.LOW if is_anom else SymptomLikelihood.NONE,
                evidence={"token_use": token_use},
            )
        )

        provider_errors = kwargs.get("provider_error_rate", 0.0)
        is_anom = _check("provider_errors", provider_errors, 0.05, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="provider_errors",
                value=provider_errors,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
                evidence={"provider_error_rate": provider_errors},
            )
        )

        retries = kwargs.get("retry_count", 0)
        is_anom = _check("retries", float(retries), 2.0, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="retries",
                value=float(retries),
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.LOW if is_anom else SymptomLikelihood.NONE,
                evidence={"retry_count": retries},
            )
        )

        queue_lag = kwargs.get("queue_lag_ms", 0.0)
        is_anom = _check("queue_lag", queue_lag, 1000.0, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="queue_lag",
                value=queue_lag,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
                evidence={"queue_lag_ms": queue_lag},
            )
        )

        return outputs
