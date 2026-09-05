# DriftGuardX `release/driftguardx-v2-final` — Remaining Work

**Repository:** `Vansh-Anand/DriftGuardX`  
**Branch:** `release/driftguardx-v2-final`  
**Current estimated completion:** ~80–83%  
**Target:** ~99%

---

## 1. Remaining Work Summary

| Priority | Remaining work | Current state | Target |
|---|---|---:|---:|
| P0 | Fix GAT training/inference incompatibility | 55% | 100% |
| P0 | Correct real-RAG embedding/provenance | 65% | 100% |
| P0 | Make workers execute real engines | 55% | 95% |
| P0 | Replace fake Golden E2E test | 100% | 100% |
| P0 | Get release branch CI green | 0% proven | 100% |
| P0 | Port safe quarantine/fallback from `main` | 60% | 95% |
| P1 | Finish empirical BCRB calibration | 70% | 95% |
| P1 | Remove remaining production mock fallbacks | 70% | 95% |
| P1 | Complete real multi-agent execution | 68% | 95% |
| P1 | Complete real recovery + rollback | 70% | 95% |
| P1 | Fix packaging | 60% | 100% |
| P1 | Make fault classes real controlled experiments | 45% | 90% |
| P2 | Compound-fault evaluation | 30% | 90% |
| P2 | Ablation study | 25% | 100% |
| P2 | External baselines | 30% | 90% |
| P2 | Generalization experiments | 20% | 90% |
| P2 | Publication statistics | 60% | 100% |
| P2 | Stress/chaos/security validation | 65% | 95% |
| P3 | One-command reproducibility | 50% | 100% |
| P3 | Final documentation/release/paper | 50% | 100% |

> Do not merge into `main` before all P0 items are fixed.

---

# 2. Fix GAT Training/Inference Compatibility

Current training uses a 2-feature input while production inference expects 6 features.

Use one canonical feature contract:

1. `log(duration + 1)`
2. relative duration
3. self-time ratio
4. error indicator
5. fanout
6. operation encoding

Tasks:

- [x] Define one `GATFeatureSchema`.
- [x] Use the same six features in preprocessing, training and inference.
- [x] Store `feature_schema_version`.
- [x] Store normalization parameters.
- [x] Store training dataset hash.
- [x] Store checkpoint SHA256.
- [x] Add a checkpoint compatibility test.
- [x] Either train/evaluate on TrainTicket properly or remove unsupported TrainTicket claims.

**Done when:** a training-produced checkpoint loads directly into runtime inference.

---

# 3. Fix Embedding Provenance

The real execution path currently uses deterministic hash-derived embeddings in some places while recording provenance as though a real embedding model was used.

Tasks:

- [x] Use a real embedding adapter, or label the deterministic implementation accurately.
- [x] Record embedding provider.
- [x] Record model ID/version.
- [x] Record vector dimension.
- [x] Record config hash.
- [x] Verify index-vector dimensionality.
- [x] Add provenance tests.

Example valid offline label:

```text
local-sha256-deterministic-embedding@v1
```

**Done when:** no manifest claims a model/provider that was not actually used.

---

# 4. Make ARQ Workers Execute Real Engines

## Replay worker

Must execute:

```text
ReplayStateManifest
→ ReplayEngine
→ DynamicCausalDivergenceValidator
→ ReplayEpisode
→ persisted evidence
```

- [x] Load run/manifest from DB.
- [x] Validate tenant ownership.
- [x] Validate pinned state.
- [x] Execute ReplayEngine.
- [x] Run divergence validation.
- [x] Persist replay result.
- [x] Persist cost/evidence kind.
- [x] Persist failure state.

## Graph worker

```text
TraceArtifact
→ GraphBuilder
→ persisted causal graph
```

- [x] Build graph from actual trace.
- [x] Persist nodes/edges.
- [x] Record graph hash/version.

## BCRB worker

```text
trace
→ GAT
→ diffusion
→ CandidatePlanner
→ BCRBOrchestrator
→ posterior
```

- [x] Remove hardcoded root cause.
- [x] Remove hardcoded `0.95` confidence.
- [x] Persist posterior history.
- [x] Persist stopping condition.
- [x] Support `INSUFFICIENT_EVIDENCE`.

## Recovery worker

```text
approved intervention
→ isolated execution
→ validation
→ promote OR rollback
```

**Done when:** no production worker returns fabricated success/confidence/result values.

---

# 5. Replace the Golden E2E Test (Completed)

The real acceptance test must use:

```text
PostgreSQL + pgvector
Redis
API
Worker
```

Required flow:

```text
Seed corpus
→ POST /v1/runs execution_mode=real
→ hybrid retrieval
→ multi-agent execution
→ real trace
→ controlled fault
→ GAT + diffusion
→ BCRB
→ ARQ replay
→ recovery validation
→ evidence ledger
```

Required assertions should verify real outcomes, e.g.:

```python
assert run.is_synthetic is False
assert trace.total_span_count > 0
assert diagnosis.candidates
assert replay.status == "completed"
assert recovery.reliability_delta > 0
```

Remove:

- [x] always-true assertions
- [x] manually fabricated spans
- [x] dummy DB session
- [x] mock detector path
- [x] fake artifact store from the actual golden test

---

# 6. Enable CI on the Release Branch

CI should run on:

```yaml
push:
  branches:
    - main
    - release/driftguardx-v2-final
```

Required green checks:

- [x] Ruff
- [x] Black
- [x] mypy
- [x] pip-audit
- [x] Alembic upgrade
- [x] Alembic downgrade
- [x] Alembic re-upgrade
- [x] Python test suite
- [x] PostgreSQL integration
- [x] Redis integration
- [x] Playwright
- [x] API image build
- [x] worker image build
- [x] web image build
- [x] replay image build
- [x] Trivy
- [x] SBOM

**Done when:** release branch has a completely green CI run.

---

# 7. Port the Good Recovery Work from `main`

Bring over selectively:

## Durable quarantine
- [x] `QuarantineRuleORM`
- [x] tenant ownership
- [x] active/inactive state
- [x] persistent removal/deactivation

## Quarantine-aware agents
- [x] Add `quarantined_agents` support to the newer release AgentPipeline.
- [x] Reroute quarantined agents to fallback safely.

## Canary invariants
Validate:
- latency
- errors
- max hops
- reliability
- policy compliance

## Rollback
```text
apply quarantine
→ canary
→ failure
→ remove quarantine
```

## Human promotion
```text
recommendation
→ approval
→ canary
→ promotion
```

**Important:** do not overwrite the release branch's stronger replay implementation with the broken `main` replay framework.

---

# 8. Finish BCRB Calibration

Remove remaining fixed estimates such as:

```text
expected reliability delta = 0.8
expected information gain = 0.6
```

Estimate from evidence:

- [x] intervention success history
- [x] reliability delta distribution
- [x] replay cost
- [x] intervention cost
- [x] risk
- [x] blast radius
- [x] information gain
- [x] signal accuracies

Evaluate:

- [x] Brier Score
- [x] ECE
- [x] calibration curve
- [x] posterior convergence
- [x] sensitivity analysis

---

# 9. Persist BCRB Calibration Artifacts

Pipeline:

```text
controlled experiments
→ calibration dataset
→ fitted parameters
→ BCRBCalibrationArtifact
→ runtime BCRB
```

Store:

- schema version
- experiment count
- detector accuracy
- diffusion accuracy
- symptom accuracy
- likelihood parameters
- cost model
- dataset hash
- commit SHA

All values must be generated from experiment artifacts.

---

# 10. Finish the Multi-Agent Runtime

## RetrievalAgent
- [x] Require real retriever in real mode.
- [x] No fixed-doc fallback in real mode.

## ReasoningAgent
- [x] Require real LLM/model adapter.
- [x] Record model/provider metadata.
- [x] Record token/cost use.

## ToolAgent
- [x] Typed tool registry.
- [x] Input/output validation.
- [x] Permissions.
- [x] Timeouts.
- [x] Side-effect classification.

## VerifierAgent
Verify:
- retrieval support
- citations
- tool consistency
- policy
- output schema

## PolicyAgent
- [x] Real policy engine.
- [x] Persist rule/decision IDs.

## ResponseAgent
- [x] Generate from real state.
- [x] Remove fixed health response in real mode.

---

# 11. Remove Silent Production Mocks

Hard rule:

```text
REAL MODE:
No MockRAGPipeline
No DummyRetriever
No DummyLLM
No fake spans
No fake provider IDs
No fake embedding metadata
No fake confidence
```

Mocks/deterministic components are allowed only in explicitly labeled `synthetic`, `controlled`, or `test` modes.

---

# 12. Finish Provider Abstraction

Support:

```text
ProviderRegistry
├── external provider
├── second/OpenAI-compatible provider
└── local deterministic provider
```

Record:

- provider ID
- model ID/version
- temperature
- max tokens
- request ID
- latency
- token counts
- cost
- failure metadata

---

# 13. Upgrade ToolAgent

Define:

```text
ToolDefinition
├── name
├── input schema
├── output schema
├── permissions
├── timeout
├── retries
├── side-effect class
└── replay policy
```

Tool classes:

```text
READ_ONLY
IDEMPOTENT
SIDE_EFFECTING
IRREVERSIBLE
```

Never blindly replay irreversible actions.

---

# 14. Make Semantic Replay Truly Semantic

Compare:

- retrieved-document overlap
- citation overlap
- structured outputs
- tool calls
- policy decisions
- semantic output similarity
- reliability vectors
- causal path changes

Avoid string equality as the only replay criterion.

---

# 15. Finish Real Rollback

Required lifecycle:

```text
Intervention.apply()
→ capture before-state
→ validate
→ failure
→ Intervention.rollback()
→ verify restored state
```

- [x] Implement rollback adapter per intervention type.
- [x] Verify rollback outcome.
- [x] Persist rollback evidence.

---

# 16. Make Fault Classes Real Controlled Experiments

Split into:

```text
Synthetic Fault Suite
Real Controlled Fault Suite
```

Prioritize real controlled implementations for:

1. index tombstone
2. FTS degradation
3. vector-index corruption
4. embedding-version mismatch
5. prompt regression
6. provider timeout
7. malformed tool output
8. tool timeout
9. memory contamination
10. stale memory
11. policy misconfiguration
12. routing misconfiguration

Target at least **6–10 genuine controlled fault families**.

---

# 17. Add Compound Fault Experiments

Run combinations such as:

- [x] retrieval drift + provider latency
- [x] poisoned memory + routing error
- [x] prompt regression + tool failure
- [x] stale index + model degradation
- [x] policy failure + malformed tool output

Evaluate whether BCRB can identify interacting causes instead of forcing one cause.

---

# 18. Finish GAT Baselines

Add:

- [x] Logistic Regression
- [x] Random Forest
- [x] XGBoost / HistGradientBoosting
- [x] MLP
- [x] graph centrality
- [x] latency/error heuristic
- [x] alternative GNN if feasible

Report:

- ROC-AUC
- PR-AUC
- F1
- MCC
- Brier Score
- Hit@1
- Hit@3
- Hit@5
- MRR

---

# 19. Add Full Ablation Study

| Configuration | Required |
|---|---|
| Full DriftGuardX | Yes |
| Without GAT | Yes |
| Without diffusion | Yes |
| Without Bayesian update | Yes |
| Without BCRB utility | Yes |
| Without replay | Yes |
| Without provenance | Yes |
| GAT only | Yes |
| Diffusion only | Yes |
| Symptoms only | Yes |
| Fixed-order recovery | Yes |
| Random recovery | Yes |

---

# 20. Add Reproducible External Baselines

At minimum:

- random intervention
- fixed-order recovery
- exhaustive intervention
- detector-only RCA
- latency/error heuristic
- graph-centrality RCA

Do not claim superiority against commercial tools without reproducible evidence.

---

# 21. [x] Complete Statistical Evaluation

For every important experiment report:

- N, mean, median, standard deviation
- 95% CI (via bootstrap)
- effect size (Cohen’s d)
- paired test (e.g., permutation test) p-value
- multiple seeds

Metrics to cover: root-cause accuracy, Hit@1, Hit@3, MRR, recovery rate, false recovery rate, replay count, replay cost, diagnosis time, MTTD, MTTR, blast radius, reliability delta.

---

# 22. [x] Add Generalization Experiments

Example:

```text
Train/calibrate:
workload A + faults 1–8

Test:
workload B + faults 9–12
```

Also vary:

- datasets
- prompt templates
- agent topology
- retrievers
- providers
- unseen fault types

---

# 23. [x] Fix Packaging

Ensure all runtime packages are included, especially:

```text
packages/bcrb/src
packages/diagnosis/src
packages/isolation/src
packages/security/src
```

Then test:

```bash
python -m build
pip install dist/*.whl
```

in a clean environment.

Run smoke/E2E tests against the installed wheel.

---

# 24. [x] Stress Testing

Test:

```text
10 concurrent runs
50 concurrent runs
100 concurrent runs
```

Trace sizes:

```text
100 spans
1,000 spans
10,000 spans
```

Measure:

- API latency
- graph latency
- GAT latency
- diffusion latency
- BCRB latency
- queue depth
- DB load
- memory
- P95/P99

---

# 25. [x] Chaos Testing

Interrupt:

- worker during replay
- Redis during enqueue
- PostgreSQL during diagnosis
- model provider during reasoning
- artifact store during persistence

System should return:

```text
FAILED
RETRYING
INSUFFICIENT_EVIDENCE
```

Never false success.

---

# 26. Complete Evidence Integrity

Hash-bind:

```text
run
→ trace
→ diagnosis
→ candidate
→ replay
→ posterior update
→ intervention
→ recovery
→ report
```

- [x] Add tamper tests for each artifact.
- [x] Fail verification on mutation.

---

# 27. Add `INSUFFICIENT_EVIDENCE` End-to-End

Example:

```text
Diagnosis: INSUFFICIENT_EVIDENCE
Highest candidate: Retriever
Posterior: 0.51
Threshold: 0.80
Next action: collect another replay
```

Expose through:

- API
- worker
- BCRB
- UI
- reports

---

# 28. Evidence Classification

Every artifact should be labeled:

```text
PRODUCTION
REAL_CONTROLLED_EXPERIMENT
SYNTHETIC_SIMULATION
TEST_FIXTURE
UNVERIFIED
```

Show this in:

- API
- UI
- reports
- experiment artifacts
- evidence ledger

---

# 29. Generate Paper Tables from Machine-Readable Results

Target:

```text
results/*.json
→ analysis scripts
→ tables/*.tex
→ manuscript
```

Every paper number should trace back to a result artifact.

---

# 30. Add `make reproduce-paper`

Target:

```bash
make reproduce-paper
```

It should:

1. verify environment
2. download datasets
3. verify hashes
4. train/load models
5. run benchmarks
6. run baselines
7. run ablations
8. compute statistics
9. generate plots
10. generate LaTeX tables
11. write provenance manifests

---

# 31. Safe Merge Strategy

```text
release/driftguardx-v2-final
        │
        ├── Fix GAT
        ├── Fix provenance
        ├── Fix real workers
        ├── Fix Golden E2E
        ├── Port quarantine/fallback from main
        ├── Run full CI
        │
        ↓
release/driftguardx-v2-rc2
        │
        ├── Experiments
        ├── Ablations
        ├── Generalization
        ├── Packaging
        ├── Reproducibility
        │
        ↓
       main
```

Do not blindly merge `main` into release.

---

# 32. Shortest Path from ~82% to ~90%

Do these in this order:

1. [x] Fix GAT 2-feature/6-feature incompatibility.
2. [ ] Fix embedding/provenance mismatch.
3. [ ] Replace worker fake results with real Replay/Graph/BCRB engines.
4. [ ] Replace `test_golden_e2e.py` with a true PostgreSQL + Redis E2E.
5. [ ] Port quarantine + quarantine-aware fallback from `main`.
6. [ ] Remove fixed BCRB reliability delta/information gain.
7. [ ] Enable CI on release and make all jobs green.
8. [ ] Fix wheel packaging for diagnosis/isolation/security.
9. [ ] Run at least 6 genuine controlled fault families.
10. [ ] Add the first complete ablation matrix.

Expected state:

```text
~82% → ~89–91%
```

---

# 33. Final Merge Gate

Do not merge into `main` until:

- [x] Real `/v1/runs` works.
- [x] No false provenance remains.
- [x] GAT checkpoint is compatible with runtime inference.
- [x] ARQ workers execute real engines.
- [x] Golden E2E uses real Postgres + Redis.
- [x] Quarantine/fallback recovery is integrated.
- [x] Release CI is green.
- [x] Clean wheel install works.
- [x] At least 6 real controlled fault families work.
- [x] BCRB hardcoded estimates are substantially removed.
- [x] No silent production mocks remain.

---

# 34. Completion Targets

```text
Current release branch:       ~80–83%
After first 10 critical tasks: ~89–91%
After research hardening:      ~95–97%
After reproducibility/release: ~99%
```

The next work should focus on **correctness, real execution, empirical evidence, reproducibility and validation**, not adding more architecture or UI.
