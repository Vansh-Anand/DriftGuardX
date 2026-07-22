"""
DriftGuard-X v2 — Generation Drift Detectors
"""
from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class GenerationDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "generation_drift_detector"

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

        faithfulness = kwargs.get("faithfulness_score", 1.0)
        is_anom = _check("faithfulness", faithfulness, 0.9, "<")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="faithfulness",
            value=faithfulness,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if faithfulness < 0.8 else (SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE),
            evidence={"faithfulness_score": faithfulness}
        ))
        
        contradiction = kwargs.get("contradiction_rate", 0.0)
        is_anom = _check("contradiction", contradiction, 0.05, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="contradiction",
            value=contradiction,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.CRITICAL if is_anom else SymptomLikelihood.NONE,
            evidence={"contradiction_rate": contradiction}
        ))
        
        refusal_rate = kwargs.get("refusal_rate", 0.0)
        is_anom = _check("refusal_rate", refusal_rate, 0.1, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="refusal_rate",
            value=refusal_rate,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
            evidence={"refusal_rate": refusal_rate}
        ))
        
        format_adherence = kwargs.get("format_adherence", 1.0)
        is_anom = _check("format_schema_adherence", format_adherence, 1.0, "<")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="format_schema_adherence",
            value=format_adherence,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
            evidence={"format_adherence": format_adherence}
        ))

        unsupported_claims = kwargs.get("unsupported_claim_rate", 0.0)
        is_anom = _check("unsupported_claim_rate", unsupported_claims, 0.1, ">")
        outputs.append(DetectorOutput(
            detector_name=self.detector_name,
            feature_name="unsupported_claim_rate",
            value=unsupported_claims,
            is_anomaly=is_anom,
            likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
            evidence={"unsupported_claim_rate": unsupported_claims}
        ))

        return outputs
