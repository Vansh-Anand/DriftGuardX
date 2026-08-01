"""
Unit tests for GATTraceDetector and SymptomRegistry GAT integration.
"""
import os
import pytest
from uuid import uuid4

from packages.detectors.src.gat_inference import GATTraceDetector, DriftGuardX_GAT
from packages.detectors.src.registry import SymptomRegistry


@pytest.fixture
def model_path():
    path = os.path.abspath("driftguardx_gat_model.pth")
    return path if os.path.exists(path) else None


@pytest.fixture
def detector(model_path):
    return GATTraceDetector(model_path=model_path)


def test_gat_model_architecture():
    """Verify PyG model initialization with correct dimensions."""
    model = DriftGuardX_GAT(in_channels=6, hidden_dim=64, num_classes=2)
    assert model is not None
    assert model.conv1 is not None
    assert model.conv2 is not None
    assert model.conv3 is not None
    assert model.classifier is not None


def test_detector_loads_weights_if_available(detector, model_path):
    """Verify detector loads weights file when present."""
    if model_path:
        assert detector.is_loaded is True
    else:
        pytest.skip("driftguardx_gat_model.pth not found in workspace")


def test_detector_clean_trace_inference(detector):
    """Verify inference on a healthy distributed trace."""
    clean_trace = [
        {"span_id": "root", "parent_id": None, "duration_ms": 50.0, "operation_name": "GET /api/v1/user", "is_error": False},
        {"span_id": "auth", "parent_id": "root", "duration_ms": 10.0, "operation_name": "ts-auth-service.check", "is_error": False},
        {"span_id": "db", "parent_id": "root", "duration_ms": 30.0, "operation_name": "ts-user-service.db_query", "is_error": False},
    ]
    result = detector.detect_trace_anomaly(clean_trace)
    assert "is_fault" in result
    assert "fault_probability" in result
    assert "predicted_class" in result
    assert result["num_spans"] == 3
    assert 0.0 <= result["fault_probability"] <= 1.0


def test_detector_faulty_trace_localization(detector):
    """Verify root cause localization on a trace containing bottlenecks."""
    faulty_trace = [
        {"span_id": "root", "parent_id": None, "duration_ms": 5000.0, "operation_name": "POST /order", "is_error": True},
        {"span_id": "child1", "parent_id": "root", "duration_ms": 4900.0, "operation_name": "ts-payment-service.pay", "is_error": True},
        {"span_id": "child2", "parent_id": "root", "duration_ms": 20.0, "operation_name": "ts-notification-service.send", "is_error": False},
    ]
    result = detector.detect_trace_anomaly(faulty_trace)
    assert len(result["root_cause_candidates"]) > 0
    top_candidate = result["root_cause_candidates"][0]
    assert top_candidate["operation_name"] == "ts-payment-service.pay"
    assert top_candidate["is_error"] is True


def test_symptom_registry_gat_integration(detector):
    """Verify registering GAT results into SymptomRegistry."""
    registry = SymptomRegistry()
    tenant_id = uuid4()
    run_id = uuid4()

    faulty_trace = [
        {"span_id": "root", "parent_id": None, "duration_ms": 5000.0, "operation_name": "POST /order", "is_error": True},
        {"span_id": "pay", "parent_id": "root", "duration_ms": 4900.0, "operation_name": "ts-payment.pay", "is_error": True},
    ]
    result = detector.detect_trace_anomaly(faulty_trace)
    
    # Force result is_fault for testing symptom registry mapping
    result["is_fault"] = True
    result["fault_probability"] = 0.85

    entries = registry.register_gat_result(tenant_id, run_id, result)
    assert len(entries) >= 1
    assert registry.get_symptoms_for_run(run_id) == entries
    assert "gat_detector" in entries[0].symptom_name
