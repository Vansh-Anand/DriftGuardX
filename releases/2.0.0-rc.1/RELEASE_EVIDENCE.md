# DriftGuard-X 2.0.0-rc.1 Release Evidence

Verification date: 2026-08-30  
Engineering status: internal release-candidate gates passed; production promotion not approved.

This is an evidence-bounded engineering record. It does not establish patentability, production safety, security certification, or real-world effectiveness.

## Completed internal engineering gates

- Every private API route requires authentication, and tenant scope is derived from the authenticated membership rather than a client-selected path or query value. An enumerating route-invariant test protects this rule.
- Production-like startup now fails closed unless HTTPS OIDC, async PostgreSQL, an explicit CORS allowlist, and sufficiently strong capability/transport secrets are configured. JIT identity provisioning is disabled by default, ambiguous multi-tenant identities are rejected, and API documentation is not exposed in production.
- Request IDs are sanitized; security and no-store headers are applied consistently; declared and streaming request bodies are bounded incrementally; internal database/authentication errors are logged without being disclosed to clients.
- Run creation has tenant-scoped idempotency. Span ingestion validates run/tenant/pipeline ownership, preserves reported status, bounds identifiers and batch size, and uses tenant-scoped span identity backed by a reversible migration.
- The deterministic mock pipeline cannot be mislabeled as real evidence. The dormant real adapter requires explicit provider and immutable provenance metadata, while production startup rejects enabling the unwired real-pipeline flag instead of silently falling back.
- Recovery validation requires replay-derived evidence plus an authenticated, unexpired, tenant-bound access context.
- Replay work uses killable process/container boundaries with incremental wall-time, resident-memory, and serialized-output enforcement before parent-process materialization.
- Replay manifests bind the original request envelope, trace, component/policy state, deterministic corpus/index state, source implementation, frozen dependency lock, and execution artifact identity; legacy literal placeholders were removed.
- Docker/ARQ entrypoints, readiness behavior, Compose migration ordering, non-root users, Kubernetes probes, and migration UID alignment were repaired. Unpublished Kubernetes images use an explicit zero-digest fail-closed promotion placeholder, not a fabricated digest.
- Synthetic simulation, controlled replay, and production canary evidence classes are distinct in contracts, API responses, UI, ledger exports, and benchmark artifacts.
- Python/UI version metadata is derived from canonical build metadata.
- `uv.lock`, hash-locked `requirements.lock`, and the npm lock are committed inputs to a content-addressed experiment manifest.
- Placeholder worker and planner paths no longer report fabricated successful work or reliability improvements; the graph UI renders authenticated evidence or an explicit unavailable state.
- The console uses an evidence-aware responsive operations shell; missing telemetry/providers remain visibly unavailable, experiment previews cannot masquerade as executed results, and isolation/version claims come from current implementation and build metadata.

## Verification results

| Gate | Result |
|---|---|
| Complete Python suite | 430 passed, 20 conditional skips |
| Release-critical strict MyPy | 32 files, no issues |
| Fatal Ruff syntax gate | Passed |
| Black release-critical formatting gate | 30 files, passed |
| Next.js 16.3.3 production build/type validation | Passed |
| Playwright browser smoke | 3 passed |
| Frozen Python dependency audit | Passed; no known vulnerabilities |
| Production web dependency audit | Passed; 0 vulnerabilities |
| Alembic disposable upgrade/check/downgrade/upgrade | Passed; no new upgrade operations |
| Compose model validation | Passed |
| Kubernetes YAML parse validation | 10 files passed |
| Frozen dependency resolution | Passed (`uv lock --check`) |

Conditional local skips cover optional ML packages, live service endpoints, and a running Docker daemon. The local Docker daemon was unavailable, so image builds and Docker isolation tests were not executed on this workstation. CI is configured to supply PostgreSQL and Redis and to run the complete suite on Python 3.11.

## Manifest-bound benchmark evidence

Evidence class for every result below: `synthetic_simulation`.

- Deterministic fault harness: 25 golden executions and 35 injected-fault executions.
- Seeded causal benchmark: seven fault classes, five strategies, three queries per fault, nineteen candidates, fixed seed 42. SciFact supplies query text, while corpus, pipeline, faults, interventions, cost, and oracle remain controlled simulations.

| Strategy | Confirmed accuracy | Localization | Confirmation | Observed mitigation | False confirmation | Mean replays | Mean cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Causal planner | 0.952 | 1.000 | 0.952 | 1.000 | 0.000 | 17.143 | $0.857 |
| Exhaustive | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 9.381 | $0.469 |
| Random | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 12.810 | $0.640 |
| Fixed order | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 9.381 | $0.469 |
| Current BCRB | 0.571 | 0.571 | 0.571 | 0.571 | 0.000 | 11.714 | $0.586 |

The corrected oracle requires the intervention target to match injected ground truth. Confirmation and actually observed mitigation are reported separately. The result does not support a cost, replay-count, blast-radius, or superiority claim for the causal planner; exhaustive and fixed-order search were cheaper in this uniform-prior synthetic harness.

## Immutable experiment record

Manifest SHA-256: `3dbf58b22bfd1d92f2558a52142893f1af6b3e6ca4e754b0516de9f185bef540`

The active JSON manifest binds the source inventory, tracked diff, dependency locks, exact commands, seed, runtime, and three result artifacts. It records a dirty working tree because this workspace has not been committed. A reviewed clean commit and signed tag are required before external release.

## External promotion gates

1. Run Docker image builds and isolation tests on a Docker-capable runner; archive test and SBOM/vulnerability-scan evidence.
2. Publish API, worker, and web images under the repository owner's registry namespace; replace each zero digest and the replay image identity with registry-produced immutable digests.
3. Validate the migration cycle and authenticated service smoke against disposable PostgreSQL/Redis services in CI.
4. Configure and test production OIDC, role synchronization, KMS/HSM-backed keys, secrets, ingress, TLS, network policy, backups, and observability.
5. Wire and independently validate a production provider/retrieval pipeline and durable external job dispatcher; both intentionally fail closed or remain outside the production API today rather than fabricating success.
6. Preregister evaluation criteria and obtain independent controlled/real replay evidence before any effectiveness claim.
7. Obtain independent penetration, load, failure-injection, privacy, licensing, and patent-counsel review before external distribution.
