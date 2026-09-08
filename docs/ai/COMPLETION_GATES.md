# Completion Gates

Status: 2026-09-08. The project remains an internal research prototype.
Use STATE.md for current verification results. Completion requires evidence for
the following gates, not simply more implemented features.

| Priority | Work | Acceptance Evidence | Dependency |
|---|---|---|---|
| 1 | Obtain a clean release CI run | All configured jobs pass for the exact reviewed source revision, including PostgreSQL migrations, Redis integration, web tests, container builds, and scans | Hosted repository and CI access |
| 2 | Publish release images | `.github/workflows/publish-release.yml` publishes and signs API, worker, replay, and web images, then uploads a digest locked Kubernetes bundle | GitHub Actions, GHCR, and package write permission |
| 3 | Configure a deployment | OIDC tenant membership, TLS, managed signing keys, secrets, backups, monitoring, and network policy are configured and tested | Target infrastructure and service configuration |
| 4 | Validate external recovery | A real integration produces authenticated traces, bounded replay evidence, authorized recovery, rollback, and a verifiable certificate | Real workload, managed keys, and bounded canary scope |
| 5 | Validate operational requirements | Independent security review, measured endpoint load, restore and failure exercises, and privacy/licensing review | Deployment, representative traffic, and reviewers |
| 6 | Broaden research evidence | Workload-specific fault injections and ablations cover model, prompt, tool, memory, routing, and policy; evidence reports include failures and uncertain results | Reproducible workloads and pinned implementations |

## Current Local Findings

- The latest complete suite had 523 passes, 23 skips, and two timing failures.
  The ledger append and simulated UI latency tests both passed when rerun alone.
  Preserve the distinction between a passing rerun and a clean full-suite run.
- tests/e2e/test_load.py measures simulated sleeps. It does not exercise the
  named endpoints and cannot establish production throughput or latency.
- The expanded retrieval experiment covers 133 fault cases across 100 queries.
  All three strategies recover in this controlled candidate set. The informed
  scheduler has the injected fault's known corrective intervention as its prior;
  this is not evidence of independent fault discovery.
- The final artifact is results/controlled_replay/scifact_bm25_multifault_verified.json.
  Its 399 trial hashes, manifest hash, and implementation hashes were checked.
  The earlier multifault artifact is an intermediate run and is retained.

## Reproduce the Retrieval Experiment

```text
uv run python scripts/download_beir.py --dataset scifact
uv run python -m apps.cli.run_controlled_replay_benchmark --max-queries 100 --fault-family relevant_document_tombstone --fault-family retriever_top_k_regression --output results/controlled_replay/scifact_bm25_multifault_new.json
```

Evidence schema 1.1.0 records selected fault families, family aggregates, and
query-level statistical comparisons. The number of baseline-evaluable queries
can exceed the number with measurable faults. Timing and source-state metadata
make complete artifact hashes run-specific. Compare measured retrieval outcomes
and replay counts for reproducibility, and verify each artifact's own digests.
