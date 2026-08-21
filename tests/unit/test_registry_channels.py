import pytest
import warnings
from uuid import uuid4
from packages.detectors.src.registry import SymptomRegistry
from packages.contracts.src.models import DetectorOutput, CausalDriftChannel, SymptomLikelihood

def test_registry_explicit_channel():
    registry = SymptomRegistry()
    run_id = uuid4()
    tenant_id = uuid4()
    
    # Detector explicitly claims RETRIEVAL
    output = DetectorOutput(
        detector_name="search_db",
        feature_name="staleness",
        value=0.9,
        likelihood=SymptomLikelihood.HIGH,
        is_anomaly=True,
        drift_channel=CausalDriftChannel.RETRIEVAL
    )
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        entry = registry.register_symptom(tenant_id, run_id, "node_1", output)
        
        assert entry.typed_causal_map.primary_channel == CausalDriftChannel.RETRIEVAL
        assert len(w) == 0

def test_registry_unknown_fallback():
    registry = SymptomRegistry()
    run_id = uuid4()
    tenant_id = uuid4()
    
    # Detector forgets to set channel
    output = DetectorOutput(
        detector_name="search_db",
        feature_name="staleness",
        value=0.9,
        likelihood=SymptomLikelihood.HIGH,
        is_anomaly=True,
        drift_channel=None
    )
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        entry = registry.register_symptom(tenant_id, run_id, "node_1", output)
        
        assert entry.typed_causal_map.primary_channel == CausalDriftChannel.UNKNOWN
        assert len(w) == 1
        assert "did not explicitly register a drift channel. Defaulting to UNKNOWN" in str(w[-1].message)
