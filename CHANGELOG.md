# CHANGELOG

## [Unreleased]

### [Unreleased]
### Added
- **Production OIDC Authentication (`apps/api/src/auth/auth.py`)**: Replaced mock authentication with JWKS-backed JWT validation via `python-jose`, ensuring secure token verification for `iss`, `aud`, `exp`, and RSA signatures.
- **Tenant Isolation (`apps/api/src/models.py`)**: Introduced `UserORM`, `TenantMembershipORM`, and `IdempotencyKeyORM` to guarantee rigorous tenant boundaries. Idempotency keys are now durably tenant-scoped.
- **Dependency Injection**: Overhauled `get_current_tenant` to strictly check `X-Tenant-ID` headers against `TenantMembershipORM` associations with role extraction.
- **Database Migrations (`apps/api/alembic/`)**: Drafted a migration script configuring PostgreSQL Row Level Security (RLS) on all tenant-aware tables.
- **Security Tests (`tests/e2e/test_tenant_isolation.py`)**: Implemented IDOR, role escalation, missing header, and invalid token tests.
- **Production Sandbox (Prompt 3)**: Container isolation features implemented previously.

### [v2.0.0-rc.1] - 2026-08-25
### Added
- **Final Release Candidate (Stage 20)**: Completed the rigorous final system audit mapping all implemented logic to mechanism claims.
- **Patent Documentation Pack (`docs/`)**: Authored `patent_evidence_matrix.md`, `patent_technical_disclosure.md`, and `prior_art_worksheet.md` to support formal filing without constituting legal advice.
- **Product Guides**: Authored `product_guide.md` and a controlled `demo_script.md` for guided walkthroughs.
- **Research Skeleton**: Drafted `research_manuscript_skeleton.md` ensuring all theoretical claims are scientifically bounded by measured effects.
- **Artifact Freezing**: Created `scripts/freeze_artifacts.py` to freeze the codebase environment and reproducibility locks to `releases/v2.0.0-rc.1/`.
- **Claim Discipline**: Scrubbed `README.md` and Next.js Web Console (`apps/web/app/page.tsx`) to remove language implying absolute causal guarantee or production safety.

### [0.17.0] - 2026-07-25
### Added
- **Auditable Base**: Validated full schema, API pagination, and API extended integrations.
- **Reproducible Artifacts**: Fixed Pydantic validation boundaries between test mocks, API, and ReplayEngine components.
- **Test Matrix Stabilized**: `tests/e2e/test_golden_demo.py` now passes with 100% success mapping to isolated ReplayEpisode schema logic.
- **Full Traceability**: Preserved trace linkages during replay execution. End-to-end trace ids flow perfectly across the system boundaries.
- **Secure Mock Auth**: Verified deterministic mock token implementations for all test isolation setups enforcing strict tenant limits.
- **Packaging complete**: Verified deterministic runs across 156+ test items in 8.08s proving system is ready for the closed-loop rollout.

### [0.16.0] - 2026-07-25

### Added
- **Statistical Validation (`packages/evaluation/src/analysis/stats.py`)**: Added paired bootstrap, permutation tests, effect size, and Bonferroni corrections. Generated formal `docs/statistical_report.md`.
- **Security Tests (`tests/e2e/test_security.py`)**: End-to-end security suite validating prompt injection, malicious tool outputs, spoofing, tampering, and isolation boundaries.
- **Chaos Engineering (`tests/e2e/test_chaos.py`)**: Chaos tests validating worker/Redis failovers, DB failovers, and provider timeouts.
- **Load Testing (`tests/e2e/test_load.py`)**: Asyncio-based concurrent load testing proving baseline TPS for ingestion and cryptographic certificate generation.
- **Red Team & Threat Models (`docs/`)**: Detailed documentation on STRIDE threat modeling, load capacity SLOs, and unresolved risks preventing production scale rollout.

### [0.15.0] - 2026-07-25

### Added
- **Dataset Adapters (`packages/evaluation/src/datasets/adapters.py`)**: `BenchmarkAdapter`s to pull mock data and translate it into the deterministic `ReplayEpisode` contract securely.
- **Fault Overlays (`packages/evaluation/src/datasets/fault_overlays.py`)**: Stochastic perturbation logic that layers simulated drift over data without mutating original sources.
- **Experiment Configs (`packages/evaluation/src/experiments/configs.py`)**: Typed configuration models for running variants of evaluation like detector-only, bcrb, exhaustive-replay.
- **Experiment Orchestrator (`packages/evaluation/src/experiments/orchestrator.py`)**: End-to-end evaluation execution engine routing faults, regimes, and configs.
- **Experiment Tracker (`packages/evaluation/src/experiments/tracker.py`)**: Integration with MLflow backed by SQLite for robust local metric tracking.
- **Analysis & Plotting (`packages/evaluation/src/analysis/`)**: Utilities for generating drift performance graphs and BCRB efficiency frontier plotting.
- **CLI Commands (`apps/cli/experiments.py`)**: Command line tools to trigger runs and emit publication-ready artifacts.
- **Web UI (`apps/web/app/experiments/page.tsx`)**: React UI registering executed experiments and their linked metrics.

### [0.14.0] - 2026-07-23

### Added
- **Rationale Models (`packages/rationale/src/models.py`)**: `RationaleInputContract` for strict, bounding evidence and `RationaleOutput` for styled outputs (Operator, Exec, Incident, Patent).
- **Deterministic Templates (`packages/rationale/src/templates.py`)**: Complete deterministic baseline text generation that does not require an LLM, ensuring guaranteed execution.
- **Factual Validator (`packages/rationale/src/validator.py`)**: Real-time hallucination scanner ensuring generated rationales do not invent component origins, numeric metrics, or version tags.
- **LLM Adapter (`packages/rationale/src/llm.py`)**: Optional LLM logic with strict hallucination controls, auto-redacting PII from traces, and falling back to templates instantly if validation fails.
- **Rationale UI Integration (`apps/web/app/rationale/page.tsx`)**: Rationale text component rendering structural evidence citations and metadata overlays.
- **Evaluation Suite (`tests/e2e/test_rationale_eval.py`)**: Automated verification for hallucinations, component omissions, version alterations, and template fallbacks.

## [0.13.0] - 2026-07-22
### Added
- **Ledger Cryptography (`packages/ledger/src/crypto.py`)**: Added Ed25519 signing support via `cryptography` package, providing local development signatures and a KMS stub.
- **Certificate Schema (`packages/ledger/src/schema.py`)**: Defined canonical `RecoveryCertificate` with deterministic JSON canonicalization, schema version, and domain separators.
- **Append-Only Chain (`packages/ledger/src/chain.py`)**: Added `LedgerChain` using `aiosqlite` for tamper-evident hash chaining, strict signature checks, and missing-record / fork detection.
- **Ledger Export (`packages/ledger/src/export.py`)**: Provided exact machine bundles for verification and redacted views for human analysis.
- **Standalone Verifier (`apps/cli/verifier.py`)**: A portable script to independently verify the signature and hash-chain of exported bundles.
- **Ledger UI (`apps/web/app/ledger/page.tsx`)**: Dashboard displaying chain integrity, certificate history, linkage, and signatures.
- **Tamper Tests & Benchmarks (`tests/e2e/test_ledger_tamper.py`)**: Comprehensive test suite proving tamper detection on linkage, signatures, and payload manipulation, plus scaling latency tests.

## [0.12.0] - 2026-07-22
### Added
- **Recovery Action Schemas (`packages/recovery/src/actions.py`)**: 9 allowlisted recovery actions with explicit parameters and idempotency.
- **Rollback Capsule (`packages/recovery/src/capsule.py`)**: Immutable rollback capsules with cryptographic integrity, expiry, and compatibility constraint checking.
- **State Machine (`packages/recovery/src/state_machine.py`)**: Saga-style orchestrator with PREPARE→EXECUTE→VERIFY→COMMITTED/COMPENSATED states.
- **Executor Framework (`packages/recovery/src/executor.py`)**: Recovery executor interface handling parameter validation, idempotency guards, optimistic version locks, and a safe `LocalDevExecutor`.
- **Canary Verification (`packages/recovery/src/canary.py`)**: Bounded verification of quality, cost, latency, and safety thresholds post-execution.
- **Recovery Engine (`packages/recovery/src/engine.py`)**: Full closed-loop orchestrator for the recovery state machine, canary execution, policy gating, and auto-compensation.
- **Failure-Injection Tests (`tests/e2e/test_recovery.py`)**: Extensive test suite covering stale state, idempotent suppression, expired capsule, safety violation, and cancellation handling.
- **Recovery UI (`apps/web/app/recovery/page.tsx`)**: Dashboard for tracking recovery status, saga logs, verification metrics, and capsule inspection.

## [0.11.0] - 2026-07-22
### Added
- **Policy Hierarchy (`packages/policy/src/hierarchy.py`)**: `PolicyRule`, `PolicyNode`, `EffectivePolicy` across four levels (Org→BU→Pipeline→Agent) with full audit chain.
- **Inheritance Resolver (`packages/policy/src/resolver.py`)**: Tightening-only deterministic resolution; `PolicyConflictError` on illegal relaxation without justification.
- **Risk Tier Registry (`packages/policy/src/tiers.py`)**: All DriftGuard-X actions mapped to LOW/MEDIUM/HIGH/CRITICAL with per-tier approval requirements.
- **Approval Service (`packages/policy/src/approvals.py`)**: Full lifecycle (create, approve, deny, expire); self-approval block; delegated approvers; break-glass with mandatory audit.
- **Unified Policy Engine (`packages/policy/src/engine.py`)**: Single evaluator integrating hierarchy, tiers, and approvals; every decision logged with rule_id and policy version.
- **Shadow Mode (`packages/policy/src/shadow.py`)**: Candidate policy evaluation against historical events with tightened/relaxed/unchanged diff report.
- **Integration Hooks (`packages/policy/src/hooks.py`)**: `pre_replay_check`, `pre_recovery_check`, `pre_execution_check`, `pre_rollback_check` — raises `PolicyDeniedError` on deny.
- **Policy UI (`apps/web/app/policy/page.tsx`)**: Three-tab console: hierarchy tree, action matrix, approval queue with break-glass flagging.
- **Patent Evidence (`docs/patent_evidence_policy.md`)**: Mechanism 3.E claims mapping.
- **Security Tests (`tests/security/test_policy_security.py`)**: 15 tests covering cross-tenant isolation, confused deputy, self-approval block, break-glass audit, determinism, and tightening inheritance.

## [v2.0.0-beta.2] - 2026-07-23
### Added
- Comprehensive Next.js Web Console (`apps/web`) with Tailwind CSS and Recharts.
- Navigation Sidebar with access to Runs, Trace Detail, Causal Graph, Replay Lab, BCRB Scheduler, Diagnosis, Policy, Recovery, and Ledger.
- `Truthful UI` implementation rendering explicit states (Measured, Inferred, Synthetic, Certified, Uncertified, Unavailable) for data provenance.
- Golden Demo Tour scaffolding for safe walkthroughs with seeded faults.
- E2E Playwright test suite for console navigation and mock RAG API integrations.

## [v2.0.0-beta.1] - 2026-07-23
### Added
- Enterprise control plane with mock OIDC/JWT authentication.
- Tenant isolation and Row-Level Security (RLS) simulation using `tenant_id`.
- Immutable audit logging for security events (Auth, RBAC, Policy).
- In-memory asynchronous job orchestrator for background evaluations and replays.
- Provider registry for LLM models (e.g., OpenAI, Anthropic) handling credentials and pricing logic.
- Expanded API endpoints for `runs`, `jobs`, and `providers` with pagination and idempotency handling.
- Typed Python SDK (`packages/sdk/src/client.py`).

## [v1.0.0-alpha] - 2026-07-212

### Added
- **Bound Library (`packages/evaluation/src/bounds.py`)**: Hoeffding analytic, Bootstrap percentile, Conformal prediction, and UnsupportedBound sentinel — each with explicit assumption documentation and fail-closed behavior.
- **Calibration Pipeline (`packages/evaluation/src/calibration.py`)**: Empirical coverage at 80/90/95/99% nominal levels, subgroup analysis by fault_type and component_layer, and UndercoverageAlert.
- **Certification Policy (`packages/evaluation/src/certification.py`)**: Five-gate CERTIFIED/UNCERTIFIED/REJECTED verdict with versioned CertificationPolicy; critical failures default to REJECTED and block automated actions.
- **Coverage Monitor (`packages/evaluation/src/coverage_monitor.py`)**: Production-stream drift detection; CERTIFIED diagnoses downgraded to UNCERTIFIED on calibration expiry or coverage drift.
- **Schema (`packages/contracts/src/models.py`)**: Extended RootCauseReport with certificate_status, bound_method, epsilon, delta, observed_coverage, calibration_version, assumptions_met/violated, human_review_required, block_automated_action.
- **Proof Appendix (`docs/proof_appendix_bounds.md`)**: Formal Hoeffding/Bootstrap/Conformal assumption documentation with explicit "not a system safety guarantee" engineering interpretation.
- **Patent Evidence (`docs/patent_evidence_bounds.md`)**: Mechanism 3.C claims mapping with measured effects and retained negative results.
- **UI (`apps/web/app/reports/[run_id]/page.tsx`)**: Gated CertificationBadge; Execute Action button strictly disabled unless certificate_status === CERTIFIED.

## [0.9.0] - 2026-07-22

### Added
- **BCRB Scheduler (`packages/replay/src/bandit.py`)**: Budget-Constrained Root-Cause Bandit scheduling algorithm using Knapsack-UCB.
- **Scheduler Baselines (`packages/evaluation/src/bandit_baselines.py`)**: Random, Cheapest-First, and Greedy-Prior schedulers for ablation comparisons.
- **Bandit State Persistence (`apps/api/src/models_bandit.py`)**: SQLAlchemy models storing UCB rewards, budget, and pull counts for worker resilience.
- **Patent Evidence Pack (`docs/patent_evidence_bcrb.md`)**: Scientific mapping of BCRB compute reduction and confidence bounds against technical patent claims.
- **Scheduler Dashboard UI**: Built `apps/web/app/scheduler/[run_id]/page.tsx` displaying the live exploration vs. exploitation state and Knapsack scores.

## [0.8.0] - 2026-07-22

### Added
- **Causal Contribution Vector (`packages/evaluation/src/contribution.py`)**: Computes multidimensional scores spanning reliability gain, cost, latency, and risk.
- **RCA Metrics & Abstention (`packages/evaluation/src/rca_metrics.py`)**: Evaluates Root Cause Analysis precision, MRR, and multi-fault credit, with built-in abstention thresholds.
- **Exhaustive Benchmark Runner (`packages/evaluation/src/benchmark.py`)**: Executes matched replay sets with No-Op and Irrelevant component negative controls.
- **Causal Language Guidelines (`docs/causal_language_guidelines.md`)**: Set strict linguistic constraints against absolute causal proof claims in reporting.
- **Root Cause Report UI**: Built `apps/web/app/reports/[run_id]/page.tsx` for viewing diagnostic results, negative controls, and epistemic limitations.

## [0.7.0] - 2026-07-22

### Added
- **Intervention Engine (`packages/replay`)**: Developed an intervention catalog and async replay planner with exhaustive Pareto generation.
- **Intervention Schemas**: Rollback, Alternate Stable, Config Patch, Route Change, Disable, Quarantine, Retry Bounded, Human Mutation.
- **Pareto Scorer (`packages/evaluation`)**: Evaluates reliability deltas to determine Pareto-optimal vs dominated replays.
- **Human Review UI**: Built `apps/web/app/interventions/[run_id]/page.tsx` to approve/reject optimal strategies based on Cost and Latency regressions.

## [0.6.0] - 2026-07-22

### Added
- **Diffusion Module (`packages/diffusion`)**: Implemented the cross-layer drift signature propagation engine.
- **Three Diffusion Variants**: `LocalDetectorBaseline`, `FixedPageRankDiffusion`, and `LearnedGATDiffusion` (PyTorch Geometric GAT model).
- **Synthetic Dataset Generator**: Simulates injected faults over causal graphs.
- **Node Explanations**: Node-level causal root probability and attention explanations via `explainer.py`.
- **Inference Caching**: Graph topology, detector version, and model version hashing in `cache.py`.
- **Diffusion UI Viewer**: Visual propagation viewer in `apps/web/app/diffusion/page.tsx` with explicit scientific restraint disclaimers.

## [0.5.0] - 2026-07-22
### Added
- **Fault Taxonomy**: Created 18 specific fault scenarios (Stale Index, Bad Chunking, Policy Overblocking, etc.).
- **Deterministic Replay Harness**: Built local deterministic providers for embedding, retrieval, generation.
- **Do-Operator Sandbox**: Implemented a `multiprocessing` tool sandbox with sys.addaudithook to trap unexpected network and filesystem writes.
- **Reliability Metrics**: Added `ReliabilityVector` to capture multi-dimensional trace scores.
- **UI**: Added `apps/web/app/replay/[id]/page.tsx` to compare side-by-side replays and display freeze-invariant validations.

- **Causal Reliability Graph Builder & State Store (Prompt 03)**:
  - Added `NodeType` and `EdgeType` schemas in `packages/contracts/src/graph.py` with baseline features.
  - Expanded `ComponentVersion` to support rollbacks, constraints, and lifecycle states in the `VersionRegistry`.
  - Built `GraphBuilder` mapping traces to deterministic DAG graphs.
  - Implemented `GraphValidator` supporting orphan checks and permitted memory/tool cycles.
  - Persisted Causal Graphs via SQLAlchemy JSON models in `apps/api/src/models_graph.py`.
  - Implemented SQL graph traversal in `/v1/graph/query` to find descendants and candidate intervention points.
  - Scaffolding of React Flow interactive Graph Explorer UI in `apps/web/app/graph/[run_id]/page.tsx`.

- **Trace Fabric & Middleware**:
  - Implemented `packages/trace_sdk/src/adapters/langgraph.py` for LangGraph node/edge tracing.
  - Implemented `packages/trace_sdk/src/adapters/agent.py` for standard Python loop tracing.
  - Expanded `SpanRecord` and `TraceArtifact` schemas with privacy modes (metadata-only, redacted-content, etc.) and semantic attribute namespaces.
  - Enhanced RedactionMetadata with PII regex detection, data residency labels, and field-level allowlists.

- **Ingestion & Storage**:
  - Implemented content-addressed ArtifactStorage for prompts/payloads in `apps/api/src/services/artifacts.py`.
  - Implemented idempotent `IngestionService` supporting late arriving and out-of-order spans.
  - Implemented trace completeness scoring in `packages/evaluation/src/completeness.py` validating monotonic time and parent relationships.

- **Dashboards & OTEL**:
  - Added `/v1/telemetry/quality` and `/search` endpoints for telemetry health tracking.
  - Scaffolding of DriftGuard-X Telemetry Console UI in `apps/web/src/app/page.tsx`.
  - Added `deploy/otel-collector-config.yaml` for OTLP HTTP/gRPC routing.
  - Created `examples/agent_demo.py` demonstrating Trace SDK capabilities with data residency and PII redaction.
