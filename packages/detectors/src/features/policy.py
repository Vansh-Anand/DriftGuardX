"""
DriftGuard-X v2 — Policy Drift Detectors
"""
from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class PolicyDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "policy_drift_detector"

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

        rule_version_changes = kwargs.get("rule_version_change_events", 0)
        is_anom = _check("rule_version_changes", float(rule_version_changes), 0, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="rule_version_changes",
            value=float(rule_version_changes),
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.LOW if is_anom else SymptomLikelihood.NONE,
            evidence={"rule_version_change_events": rule_version_changes}
        ))
        
        unexpected_allow = kwargs.get("unexpected_allow_rate", 0.0)
        is_anom = _check("unexpected_allow_rate", unexpected_allow, 0.05, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="unexpected_allow_rate",
            value=unexpected_allow,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
            evidence={"unexpected_allow_rate": unexpected_allow}
        ))
        
        risk_tier_mismatch = kwargs.get("risk_tier_mismatch_rate", 0.0)
        is_anom = _check("risk_tier_mismatch", risk_tier_mismatch, 0.01, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="risk_tier_mismatch",
            value=risk_tier_mismatch,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if is_anom else SymptomLikelihood.NONE,
            evidence={"risk_tier_mismatch_rate": risk_tier_mismatch}
        ))
        
        return outputs
