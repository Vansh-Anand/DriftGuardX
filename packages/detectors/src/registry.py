"""
DriftGuard-X v2 — Symptom Registry
"""
from typing import List
from uuid import UUID

from packages.contracts.src.models import (
    DetectorOutput, 
    SymptomLikelihood, 
    SymptomRegistryEntry,
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

    def clear(self):
        self._entries.clear()
