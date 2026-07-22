"""
DriftGuard-X v2 — Memory Drift Detectors
"""
from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class MemoryDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "memory_drift_detector"

    def evaluate(
        self, 
        trace_or_span: Any, 
        thresholds: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> list[DetectorOutput]:
        from packages.detectors.src.baselines import check_threshold
        thresholds = thresholds or {}
        outputs = []
        
        def _check(feature: str, val: float, default_t: float, default_op: str) -> bool:
            t = thresholds.get(feature)
            if t:
                return check_threshold(val, t.threshold_value, t.operator)
            return check_threshold(val, default_t, default_op)

        stale_memory = kwargs.get("stale_memory_hits", 0)
        is_anom = _check("stale_memory", float(stale_memory), 0, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="stale_memory",
            value=float(stale_memory),
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
            evidence={"stale_memory_hits": stale_memory}
        ))
        
        conflicting_memory = kwargs.get("conflicting_memory_ratio", 0.0)
        is_anom = _check("conflicting_memory", conflicting_memory, 0.1, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="conflicting_memory",
            value=conflicting_memory,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
            evidence={"conflicting_memory_ratio": conflicting_memory}
        ))
        
        poison_signatures = kwargs.get("poison_signature_matches", 0)
        is_anom = _check("poison_signatures", float(poison_signatures), 0, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="poison_signatures",
            value=float(poison_signatures),
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if is_anom else SymptomLikelihood.NONE,
            evidence={"poison_signature_matches": poison_signatures}
        ))
        
        cross_tenant_contamination = kwargs.get("cross_tenant_access_attempts", 0)
        is_anom = _check("cross_tenant_contamination", float(cross_tenant_contamination), 0, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="cross_tenant_contamination",
            value=float(cross_tenant_contamination),
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if is_anom else SymptomLikelihood.NONE,
            evidence={"cross_tenant_access_attempts": cross_tenant_contamination}
        ))

        return outputs
