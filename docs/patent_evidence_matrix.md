# Patent Evidence Matrix
*PRIVATE - NOT LEGAL ADVICE - CONFIDENTIAL PROTOTYPE DISCLOSURE*

This document maps the core mechanisms of DriftGuard-X to explicit, working code, endpoints, tests, and known limitations to substantiate claims for patent preparation.

| Mechanism / Claim Element | Source File / Implementation | API Endpoint / Interface | Tests & Evidence | Measured Effect / Known Limitation |
| :--- | :--- | :--- | :--- | :--- |
| **Trace Fabric & Provenance** | `packages/trace_sdk/src/adapters/` | `/v1/runs`, `/v1/telemetry/quality` | `tests/e2e/test_telemetry_fabric.py` | Provenance tracked successfully. Limitation: Assumes deterministic execution; asynchronous multi-agent tracing not yet exhaustive. |
| **Causal Graph Construction** | `packages/contracts/src/graph.py` | `/v1/graph/query` | `tests/e2e/test_graph_properties.py` | DAG structure generated automatically. Limitation: Cyclic tool usage currently fails closed (unsupported). |
| **Six-Layer Drift Propagation** | `packages/diffusion/src/` | N/A (Internal engine) | `tests/e2e/test_rca_baseline.py` | Identifies downstream propagation via GAT/PageRank. Limitation: GAT model requires large historical trace volume to converge. |
| **Intervention Catalog** | `packages/recovery/src/actions.py` | N/A (Internal engine) | `tests/e2e/test_intervention_engine.py` | Idempotent strategies for rollback/retry. Limitation: Requires strict component versioning; non-versioned endpoints cannot be recovered. |
| **BCRB (Budget-Constrained Bandit)** | `packages/replay/src/bandit.py` | `apps/web/app/scheduler/[run_id]` | `tests/e2e/test_bcrb_scheduler.py` | Explores interventions bounded by cost. Limitation: Knapsack approximation algorithm; does not guarantee absolute global minimum cost. |
| **Certified Analytical Bounds** | `packages/evaluation/src/bounds.py` | `/v1/runs/{id}` | `tests/e2e/test_bounds_calibration.py` | Provides Hoeffding/Bootstrap confidence bounds. Limitation: Not a safety guarantee; assumes i.i.d properties matching the calibration set. |
| **Policy Inheritance & Gating** | `packages/policy/src/engine.py` | `/v1/policy/evaluate` | `tests/security/test_policy_security.py` | Enforces hierarchical, tightening-only approvals. Limitation: Break-glass features bypass bounds, though audited. |
| **Recovery State Machine** | `packages/recovery/src/state_machine.py`| `/v1/recovery/execute` | `tests/e2e/test_recovery.py` | PREPARE->EXECUTE->VERIFY saga. Limitation: Optimistic locks might fail under heavy concurrent mutation. |
| **Cryptographic Ledger** | `packages/ledger/src/chain.py` | `apps/cli/verifier.py` | `tests/e2e/test_ledger_tamper.py` | Ed25519 hash chain for certificates. Limitation: Ed25519 signing becomes a CPU bottleneck under high concurrent volume. |
| **Deterministic Rationale** | `packages/rationale/src/templates.py` | `/v1/reports/{id}` | `tests/e2e/test_rationale_eval.py` | Generates rationale without LLM hallucination. Limitation: Template output is inflexible compared to generative text. |
| **Exhaustive Evaluation** | `packages/evaluation/src/benchmark.py` | `apps/cli/experiments.py` | `tests/e2e/test_experiments.py` | Compares negative controls to BCRB. Limitation: Compute intensive, requires `sqlite` persistence due to scale. |

> [!WARNING]
> This matrix lists *implemented and tested* features only. Any claim of broad "Guaranteed recovery" or "Certified AI Safety" beyond the measured mathematical bounds described herein is explicitly rejected by the engineering team.
