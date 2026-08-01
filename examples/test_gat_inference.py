"""
Test script to verify loading driftguardx_gat_model.pth and running GAT inference.
"""
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.detectors.src.gat_inference import GATTraceDetector

def test_inference():
    model_path = os.path.abspath("driftguardx_gat_model.pth")
    print(f"Loading model from: {model_path}")
    detector = GATTraceDetector(model_path=model_path)
    
    if not detector.is_loaded:
        print("[FAIL] Model weights failed to load!")
        return

    print("[SUCCESS] GAT Model weights loaded successfully!")
    
    # 1. Test a Clean/Normal Distributed Trace
    clean_trace = [
        {"span_id": "span_root", "parent_id": None, "duration_ms": 45.2, "operation_name": "GET /api/v1/tickets", "is_error": False},
        {"span_id": "span_auth", "parent_id": "span_root", "duration_ms": 12.1, "operation_name": "ts-auth-service.verify", "is_error": False},
        {"span_id": "span_query", "parent_id": "span_root", "duration_ms": 28.4, "operation_name": "ts-ticket-service.query", "is_error": False},
        {"span_id": "span_db", "parent_id": "span_query", "duration_ms": 15.0, "operation_name": "Postgres.SELECT", "is_error": False},
    ]
    
    clean_res = detector.detect_trace_anomaly(clean_trace)
    print("\n--- Clean Trace Detection ---")
    print(f"Is Fault: {clean_res['is_fault']} (Prob: {clean_res['fault_probability']:.4f})")
    print(f"Predicted Class: {clean_res['predicted_class']}")
    
    # 2. Test a Faulty Trace (Simulating bottleneck/error on ts-payment-service)
    faulty_trace = [
        {"span_id": "span_order_root", "parent_id": None, "duration_ms": 5200.0, "operation_name": "POST /api/v1/preserve", "is_error": True},
        {"span_id": "span_order_svc", "parent_id": "span_order_root", "duration_ms": 5150.0, "operation_name": "ts-order-service.create", "is_error": True},
        {"span_id": "span_payment", "parent_id": "span_order_svc", "duration_ms": 5000.0, "operation_name": "ts-payment-service.pay", "is_error": True},
        {"span_id": "span_notif", "parent_id": "span_order_svc", "duration_ms": 15.0, "operation_name": "ts-notification-service.send", "is_error": False},
    ]
    
    faulty_res = detector.detect_trace_anomaly(faulty_trace)
    print("\n--- Faulty Trace Detection ---")
    print(f"Is Fault: {faulty_res['is_fault']} (Prob: {faulty_res['fault_probability']:.4f})")
    print(f"Predicted Class: {faulty_res['predicted_class']}")
    print("Top Root-Cause Candidates:")
    for candidate in faulty_res['root_cause_candidates']:
        print(f"  - {candidate['operation_name']} (Self-Time Ratio: {candidate['self_time_ratio']:.2f}, Error: {candidate['is_error']})")

if __name__ == "__main__":
    test_inference()
