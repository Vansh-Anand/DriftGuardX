"""
DriftGuard-X v2 — Retrieval Drift Detectors
"""

from typing import Any

from packages.contracts.src.models import DetectorOutput, SymptomLikelihood
from packages.detectors.src.core import DriftDetector


class RetrievalDriftDetector(DriftDetector):
    @property
    def detector_name(self) -> str:
        return "retrieval_drift_detector"

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

        overlap_score = kwargs.get("top_k_overlap", 1.0)
        is_anom = _check("top_k_overlap", overlap_score, 0.5, "<")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="top_k_overlap",
                value=overlap_score,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
                evidence={"overlap": overlap_score},
            )
        )

        ks_p_value = kwargs.get("score_distribution_ks_p_value", 1.0)
        is_anom = _check("score_distribution_shift", ks_p_value, 0.05, "<")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="score_distribution_shift",
                value=ks_p_value,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
                evidence={"ks_p_value": ks_p_value},
            )
        )

        doc_age_days = kwargs.get("avg_doc_age_days", 10.0)
        is_anom = _check("document_freshness", doc_age_days, 180, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="document_freshness",
                value=doc_age_days,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.LOW if is_anom else SymptomLikelihood.NONE,
                evidence={"avg_doc_age_days": doc_age_days},
            )
        )

        stale_evidence = kwargs.get("stale_evidence_ratio", 0.0)
        is_anom = _check("stale_evidence_exposure", stale_evidence, 0.2, ">")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="stale_evidence_exposure",
                value=stale_evidence,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.MEDIUM if is_anom else SymptomLikelihood.NONE,
                evidence={"stale_evidence_ratio": stale_evidence},
            )
        )

        citation_support = kwargs.get("citation_support_ratio", 1.0)
        is_anom = _check("citation_support", citation_support, 0.8, "<")
        outputs.append(
            DetectorOutput(
                detector_name=self.detector_name,
                feature_name="citation_support",
                value=citation_support,
                is_anomaly=is_anom,
                likelihood=SymptomLikelihood.HIGH if is_anom else SymptomLikelihood.NONE,
                evidence={"citation_support_ratio": citation_support},
            )
        )

        return outputs
