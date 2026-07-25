# ADR 005: Final Release Packaging and Claim Discipline

## Status
Accepted

## Context
DriftGuard-X v2 has successfully implemented all theoretical constructs (BCRB, Graph Diffusion, Policy, Cryptographic Recovery). However, prior to release, it is essential that claims surrounding causality, safety, and operational guarantees are bounded. Exaggerated claims risk premature IP invalidation and violate the scientific integrity of a research prototype.

## Decision
We enforce a strict "Claim Discipline" architecture:
1. All theoretical assertions of causality are documented as *measured effects* on the evaluated DAG topology, not absolute proofs of system-wide safety.
2. The UI and README now contain explicit warnings clarifying that the platform is an experimental evaluation tool.
3. Patent-specific documentation (`patent_evidence_matrix.md`, `patent_technical_disclosure.md`) is logically separated from product usage documentation and is not meant to be read as legal clearance.
4. Reproducibility artifacts (`pip freeze`, commit hashes) are frozen automatically to lock the baseline performance metrics before any patent filing strategy is executed.

## Consequences
- **Positive**: Protects IP strategy by managing disclosure depth. Validates mathematical claims by scoping them correctly.
- **Negative**: The UI presents aggressive "warnings" that may make the prototype appear brittle to non-technical users, but this is an accepted tradeoff for research integrity.
