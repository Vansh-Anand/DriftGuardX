"""
DriftGuard-X v2 — Tool Drift Detectors
"""
from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class ToolDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "tool_drift_detector"

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

        tool_selection_change = kwargs.get("tool_selection_change_score", 0.0)
        is_anom = _check("tool_selection_change", tool_selection_change, 0.5, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="tool_selection_change",
            value=tool_selection_change,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
            evidence={"tool_selection_change_score": tool_selection_change}
        ))
        
        schema_mismatch = kwargs.get("schema_mismatch_count", 0)
        is_anom = _check("schema_version_mismatch", float(schema_mismatch), 0, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="schema_version_mismatch",
            value=float(schema_mismatch),
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if is_anom else SymptomLikelihood.NONE,
            evidence={"schema_mismatch_count": schema_mismatch}
        ))
        
        argument_validation_fail = kwargs.get("argument_validation_fail_rate", 0.0)
        is_anom = _check("argument_validation_failure", argument_validation_fail, 0.05, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="argument_validation_failure",
            value=argument_validation_fail,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
            evidence={"argument_validation_fail_rate": argument_validation_fail}
        ))
        
        timeout_rate = kwargs.get("timeout_rate", 0.0)
        is_anom = _check("timeout", timeout_rate, 0.01, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="timeout",
            value=timeout_rate,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
            evidence={"timeout_rate": timeout_rate}
        ))

        return outputs
