"""
DriftGuard-X v2 — Symptom Registry
"""
from typing import List
from uuid import UUID

from packages.contracts.src.models import (
    DetectorOutput, 
    SymptomLikelihood, 
    SymptomRegistryEntry,
    TypedCausalMap,
    CausalDriftChannel,
    _new_uuid,
    _utcnow
)


class SymptomRegistry:
    """In-memory or persistent registry mapping detector outputs to graph nodes."""
    
    def __init__(self):
        self._entries: List[SymptomRegistryEntry] = []
        
    def register_symptom(
        self, 
        tenant_id: UUID, 
        run_id: UUID, 
        graph_node_id: str, 
        detector_output: DetectorOutput,
        detector_version: str = "v1"
    ) -> SymptomRegistryEntry:
        """Register a new symptom if it's an anomaly."""
        # Only register if it breaches threshold or is explicitly marked anomaly
        if not detector_output.is_anomaly:
            return None
            
        # Semantic-Causal Drift Decomposition (Update 2)
        # Use explicit drift_channel from DetectorOutput if provided, fallback to UNKNOWN
        if detector_output.drift_channel:
            channel = CausalDriftChannel(detector_output.drift_channel)
        else:
            import warnings
            warnings.warn(f"Detector {detector_output.detector_name} did not explicitly register a drift channel. Defaulting to UNKNOWN.")
            channel = CausalDriftChannel.UNKNOWN
            
        typed_map = TypedCausalMap(
            primary_channel=channel,
            channel_scores={channel: detector_output.value},
            containment_partition_id=graph_node_id
        )
            
        entry = SymptomRegistryEntry(
            id=_new_uuid(),
            tenant_id=tenant_id,
            run_id=run_id,
            graph_node_id=graph_node_id,
            symptom_name=f"{detector_output.detector_name}.{detector_output.feature_name}",
            severity=SymptomLikelihood(detector_output.likelihood),
            detector_version=detector_version,
            evidence_snippet=str(detector_output.evidence),
            uncertainty=0.1,  # Baseline uncertainty
            typed_causal_map=typed_map,
            detected_at=_utcnow()
        )
        self._entries.append(entry)
        return entry

    def get_symptoms_for_run(self, run_id: UUID) -> List[SymptomRegistryEntry]:
        """Fetch all symptoms for a specific run."""
        return [e for e in self._entries if e.run_id == run_id]

    def get_symptoms_for_node(self, run_id: UUID, graph_node_id: str) -> List[SymptomRegistryEntry]:
        """Fetch symptoms localized to a specific node."""
        return [e for e in self._entries if e.run_id == run_id and e.graph_node_id == graph_node_id]

    def register_gat_result(
        self,
        tenant_id: UUID,
        run_id: UUID,
        gat_result: dict,
        detector_version: str = "gat-v1"
    ) -> List[SymptomRegistryEntry]:
        """Convert GAT detector results into symptom registry entries."""
        created_entries = []
        if not gat_result.get("is_fault", False) and not gat_result.get("root_cause_candidates"):
            return created_entries

        prob = gat_result.get("fault_probability", 0.0)
        likelihood = SymptomLikelihood.HIGH if prob > 0.7 else (SymptomLikelihood.MEDIUM if prob > 0.4 else SymptomLikelihood.LOW)

        for candidate in gat_result.get("root_cause_candidates", []):
            node_id = candidate.get("span_id", "unknown_span")
            entry = SymptomRegistryEntry(
                id=_new_uuid(),
                tenant_id=tenant_id,
                run_id=run_id,
                graph_node_id=node_id,
                symptom_name=f"gat_detector.trace_anomaly.{candidate.get('operation_name', 'op')}",
                severity=likelihood,
                detector_version=detector_version,
                evidence_snippet=f"Self-time ratio: {candidate.get('self_time_ratio', 0.0):.2f}, error: {candidate.get('is_error', False)}, prob: {prob:.3f}",
                uncertainty=round(1.0 - prob, 3),
                detected_at=_utcnow()
            )
            self._entries.append(entry)
            created_entries.append(entry)
        return created_entries

    def clear(self):
        self._entries.clear()
