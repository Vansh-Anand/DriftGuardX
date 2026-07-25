# ADR 017: Experimental Orchestration & Dataset Isolation

## Status
Accepted

## Context
DriftGuard-X requires rigorous, reproducible experimental validation of its root cause analysis and recovery capabilities. However, combining external datasets (with specific licenses) into our test tree violates internal IP isolation rules, and merging disparate evaluation regimes (e.g. tool-use vs RAG) creates uninterpretable headline scores.

## Decision
1. **Dynamic Adapters**: All external data is fetched and formatted purely in-memory via `BenchmarkAdapter` patterns.
2. **Deterministic Fault Overlays**: Rather than storing duplicated datasets with hardcoded drift, we apply seeded perturbations via `FaultOverlay` just prior to run execution.
3. **MLflow Tracking**: We will log parameters and results via an embedded MLflow store to ensure reproducible provenance for all published charts.
4. **Regime Strictness**: `ExperimentConfig` strictly enforces singular evaluation regimes per run, preventing mixed results.

## Consequences
- Reduced repository size (no large dataset caching).
- Strict adherence to 3rd-party data licenses (we only distribute the adapter, not the data).
- Reproducible benchmarking via deterministic seeds.
