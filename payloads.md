## Exact Canonical Descriptor Payload
`json
{
  "calibration_evidence": {
    "confidence_level": 0.95,
    "dataset": "test_set_1",
    "evaluator": "system",
    "metric": "accuracy",
    "sample_size": 1000,
    "source_result": 0.9,
    "target_result": null,
    "time": "2026-08-29T05:48:02.917928Z"
  },
  "captured_at": "2026-08-29T05:48:02.918052Z",
  "causal_graph_hash": "graph_A",
  "data_distribution_fingerprint": "hash_A",
  "environment_id": "ac27b20f-c2e0-4e77-96dd-22286d47516c",
  "execution_configuration": {
    "timeout": 30
  },
  "index": "docs_v1",
  "memory": "redis",
  "model": "gpt-4",
  "policy": "strict",
  "prompt": "v1",
  "provenance_hash": "prov_A",
  "retriever": "bm25",
  "tenant_id": "tenant_A",
  "tools": [
    "search",
    "calc"
  ]
}
`
## Exact Canonical Decision Payload
`json
{
  "confidence_metadata": {
    "evidence_strength": "cryptographic",
    "footprint_components_checked": 1,
    "footprint_edges_checked": 1
  },
  "created_at": "2026-08-29T05:48:02.918498Z",
  "decision_schema_version": "1.0",
  "explanation": "All recovery mechanism assumptions are preserved in the target environment.",
  "footprint_hash": "0e4a447438cf2c9c28bc22d9269e4356595046db3e60e51a2138e58a8ef23bf8",
  "policy_version": "2.0",
  "preserved_conditions": [
    "all_environment_variables"
  ],
  "recovery_id": "rec_1",
  "required_target_experiments": [],
  "source_descriptor_signature": "iYlW6adb2cR0adCvAjr/c22KzUMTamlvqDiT44oEQzs=",
  "source_environment": "ac27b20f-c2e0-4e77-96dd-22286d47516c",
  "status": "DIRECTLY_TRANSPORTABLE",
  "target_descriptor_signature": "Ellf7sOgpW9cg+Kk41R9ZfqjxxvyZREtVbS69LIbbDg=",
  "target_environment": "7106dec1-2968-42ec-b11a-1c382c72c901",
  "unknown_conditions": [],
  "violated_conditions": []
}
`
