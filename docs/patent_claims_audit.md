# DriftGuard-X Claim Support Audit

**Purpose:** technical support record for patent counsel. This document does not determine patentability and does not replace a prior-art, inventorship, or filing review.

## Implemented claim elements

| Claim family | Implemented mechanism | Primary source | Verification |
|---|---|---|---|
| Trace graph and features | Span-derived dependency graph and six-feature detector contract | `packages/detectors/src/trace_features.py`, `packages/detectors/src/gat_inference.py` | `tests/unit/test_dag_propagation.py`, `tests/integration/test_gat_api.py` |
| Three-stage graph inference | GATConv layers with 4/4/1 heads, layer normalization, mean/max pooling | `packages/detectors/src/gat_inference.py` | `tests/integration/test_gat_api.py`, `tests/unit/test_detector_calibration.py` |
| Budgeted replay selection | Candidate arms, UCB-style exploration, cost-aware selection, online updates | `packages/replay/src/bandit.py`, `packages/rag_benchmark/src/controlled_replay.py` | `tests/unit/test_bcrb_orchestrator.py`, `tests/unit/test_controlled_replay_benchmark.py` |
| Evidence-bounded evaluation | Hoeffding, bootstrap, conformal result objects and unsupported sentinel | `packages/evaluation/src/bounds.py` | `tests/unit/test_bounds.py`, `tests/unit/test_calibration.py` |
| Replay containment | Spawned subprocess, incremental bounded output, timeout, memory checks, CPython audit hook | `packages/replay/src/sandbox.py` | `tests/unit/test_sandbox.py`, `tests/e2e/test_container_sandbox.py` |
| ARC operation handling | Monkey-patched socket, shell, and subprocess calls routed to an in-process quarantine sink | `packages/replay/src/arc_isolator.py` | `tests/e2e/test_arc_isolator.py` |
| Staged mutation control | Trace-bound escrow with commit and rollback paths | `packages/replay/src/vti_coordinator.py` | `tests/e2e/test_vti_2pc.py`, `tests/integration/test_manifest_integration.py` |
| Tightening policy hierarchy | Organization, Business Unit, Pipeline, Agent levels with restrictive resolution | `packages/policy/src/hierarchy.py`, `packages/policy/src/resolver.py` | `tests/security/test_policy_security.py` |
| Approval controls | Risk tiers, distinct approvers, self-approval rejection, break-glass audit metadata | `packages/policy/src/tiers.py`, `packages/policy/src/approvals.py` | `tests/security/test_policy_security.py`, `tests/integration/test_security_audit.py` |
| Signed evidence ledger | Ed25519 certificate signatures and append-only SHA-256-linked certificate chain | `packages/ledger/src/crypto.py`, `packages/ledger/src/chain.py` | `tests/security/test_evidence_integrity.py`, `tests/e2e/test_ledger_tamper.py` |

## Scope corrections required for counsel

- The replay boundary is a restricted subprocess with CPython audit hooks and platform-dependent resource limits, not a kernel security boundary.
- ARC uses a thread-safe in-process quarantine sink in this implementation; it is not a hardware data sink.
- Statistical intervals expose assumptions and unsupported results. Conformal coverage is conditional on exchangeability assumptions; no universal coverage or recovery guarantee is claimed.
- Controlled replay evidence is limited to declared datasets, fault families, seeds, and metrics. It is not production-canary evidence and does not establish broad benchmark superiority.
- VTI currently provides an in-memory escrow/coordinator abstraction. Durable database atomicity and concurrent-reader isolation require deployment-specific enforcement.
- The four policy levels and four risk tiers are implemented enums/configuration, not a claim that every deployment must use exactly those values.

## External work still required

Patent counsel must perform a prior-art search, select claim scope, verify inventorship and disclosure dates, prepare figures and formal claims, and decide whether to file provisional or non-provisional materials. Engineering still needs hosted CI, production container/KMS/TLS controls, independent security testing, and real canary evidence before any production-readiness statement.
