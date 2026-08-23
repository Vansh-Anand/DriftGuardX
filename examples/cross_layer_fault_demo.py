"""
DriftGuard-X v2 - Cross-Layer Fault Demonstration (Prompt 05)
"""
from uuid import uuid4

from packages.detectors.src.features.generation import GenerationDriftDetector
from packages.detectors.src.features.retrieval import RetrievalDriftDetector
from packages.detectors.src.registry import SymptomRegistry


def main():
    print("--- DriftGuard-X: Cross-Layer Fault Demonstration ---\n")

    tenant_id = uuid4()
    run_id = uuid4()
    registry = SymptomRegistry()

    # 1. Retrieval Layer execution
    print("1. Executing Retrieval Layer...")
    retriever_detector = RetrievalDriftDetector()

    # Simulate a fault: very low top-k overlap because the index was stale
    retrieval_trace = {
        "top_k_overlap": 0.1,  # Threshold is 0.5
        "avg_doc_age_days": 200.0, # Threshold is 180
    }

    retrieval_symptoms = retriever_detector.evaluate(trace_or_span=None, **retrieval_trace)
    for sym in retrieval_symptoms:
        if sym.is_anomaly:
            print(f"  [!] {sym.feature_name} Anomaly Detected: {sym.value}")
            registry.register_symptom(
                tenant_id=tenant_id,
                run_id=run_id,
                graph_node_id="retriever:span_1",
                detector_output=sym
            )

    # 2. Generation Layer execution
    print("\n2. Executing Generation Layer (downstream of Retrieval)...")
    generator_detector = GenerationDriftDetector()

    # Simulate the causal effect: because the retrieved docs were bad, the generator hallucinated
    generation_trace = {
        "unsupported_claim_rate": 0.25, # Threshold is 0.1
        "contradiction_rate": 0.0,
        "faithfulness_score": 0.75, # Threshold is 0.9
    }

    generation_symptoms = generator_detector.evaluate(trace_or_span=None, **generation_trace)
    for sym in generation_symptoms:
        if sym.is_anomaly:
            print(f"  [!] {sym.feature_name} Anomaly Detected: {sym.value}")
            registry.register_symptom(
                tenant_id=tenant_id,
                run_id=run_id,
                graph_node_id="generator:span_2",
                detector_output=sym
            )

    # 3. View Registry
    print("\n3. Symptom Registry State for Run:")
    symptoms = registry.get_symptoms_for_run(run_id)
    for s in symptoms:
        print(f"  -> {s.detected_at.isoformat()} | {s.symptom_name} ({s.severity.upper()}) @ {s.graph_node_id}")

    print("\nDemonstration complete: The retrieval fault successfully cascaded and registered symptoms across multiple layers.")

if __name__ == "__main__":
    main()
