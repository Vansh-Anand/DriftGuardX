# DriftGuard-X 2.0.0-rc.1 Release Evidence

Verification date: 2026-09-01
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
- The public experience now uses an editorial motion system with cinematic data media, responsive asymmetric case layouts, route transitions, reduced-motion support, adaptive navigation, and mobile overflow protection. Bundled third-party media is documented in a source/license attribution record and is never presented as system evidence.

## Verification results

| Gate | Result |
|---|---|
| Complete Python suite | 444 passed, 20 conditional skips |
| Release-critical strict MyPy | 39 files, no issues |
| Fatal Ruff syntax gate | Passed |
| Black release-critical formatting gate | 37 files, passed |
| Next.js 16.3.3 production build/type validation | Passed |
| Playwright browser smoke | 5 passed, including editorial landing and mobile composition |
| Frozen Python dependency audit | Passed; no known vulnerabilities |
| Production web dependency audit | Passed; 0 vulnerabilities |
| Trivy HIGH/CRITICAL policy + Syft SBOM | Passed; actionable scanner findings: 0 |
| PostgreSQL upgrade/check/downgrade/upgrade | Passed; model and migration metadata in parity |
| API, worker, replay, and web container builds | Passed on GitHub-hosted Linux runners |
| Compose model validation | Passed |
| Kubernetes YAML parse validation | 10 files passed |
| Frozen dependency resolution | Passed (`uv lock --check`) |

Conditional skips cover optional ML packages, live external provider endpoints,
and container replay tests that require a published digest-pinned replay image.
The local Docker daemon was unavailable, but GitHub CI supplied pgvector-enabled
PostgreSQL and Redis, executed the complete suite on Python 3.11, built all four
Linux images, generated an SBOM, and enforced the vulnerability policy. Definitive
run: `33517126647` (`6910da748402aa2d1619a07dbfe0fa12dab88615`).

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

## Real-data controlled replay evidence

Evidence class: `controlled_replay`.

An additional offline benchmark executed a deterministic BM25 retrieval workload
over a hash-pinned BEIR/SciFact snapshot: 5,183 scientific documents, 1,109
queries, and the official test qrels. One hundred queries for which the clean
retriever found at least one relevant document were evaluated. The harness
tombstoned each query's relevant index entries, then re-executed candidate
interventions until retrieval recall returned to the clean baseline.

| Strategy | Recovery rate | Mean replays | Paired replay delta vs BCRB | 95% paired bootstrap CI | Randomization p-value |
|---|---:|---:|---:|---:|---:|
| BCRB with index-integrity prior | 1.000 | 1.000 | — | — | — |
| Fixed order | 1.000 | 4.000 | +3.000 | [3.000, 3.000] | <0.001 |
| Seeded random | 1.000 | 2.320 | +1.320 | [1.120, 1.520] | <0.001 |

The BCRB prior is supplied by the controlled `index_snapshot_digest_changed`
fault signature. The qrels define both relevance and the tombstoned documents.
Consequently, this result supports only the narrow claim that an integrity signal
can reduce replay count for this retrieval fault family. It does not establish
general BCRB or causal-planner superiority, full RAG effectiveness, live-system
safety, or production recovery. Host-specific elapsed time is recorded but is not
the primary comparison metric.

Every trial contains a canonical SHA-256 evidence digest. The complete artifact
binds dataset file hashes, experiment parameters, source state, aggregates,
paired statistics, and trial evidence under manifest SHA-256
`337f496e8b25d889ed7d21ab241a381b8c6ba1a5c8a7ff7b67e76e4cff74ad8a`.
The artifact was regenerated from clean source commit
`afdd841f8a5c7a3ee0d3662d3df149e156f83bb5`; its tracked-diff digest is the
SHA-256 of an empty byte sequence. The manual CI evidence workflow independently
regenerates the experiment from clean checkout and rejects dirty provenance
before retaining its artifact.

## Immutable experiment record

The controlled-replay artifact manifest SHA-256 is
`337f496e8b25d889ed7d21ab241a381b8c6ba1a5c8a7ff7b67e76e4cff74ad8a`.
It binds the clean benchmark source commit, pinned SciFact file hashes, exact
parameters, aggregates, paired statistics, and all 300 trial digests. The
software dependency lock was subsequently security-hardened and verified in CI;
the historical benchmark artifact remains immutable and is not relabeled as a
run of the later software commit.

## External promotion gates

1. Publish API, worker, web, and replay images under the repository owner's registry namespace; replace each zero digest with registry-produced immutable digests and rerun the container replay isolation tests against that digest.
2. Configure and test production OIDC, role synchronization, KMS/HSM-backed keys, secrets, ingress, TLS, network policy, backups, and observability.
3. Wire and independently validate a production provider/retrieval pipeline and durable external job dispatcher; both intentionally fail closed or remain outside the production API today rather than fabricating success.
4. Preregister evaluation criteria and obtain independent controlled replay across additional fault families, plus production-canary evidence, before any broad effectiveness claim.
5. Obtain independent penetration, load, failure-injection, privacy, licensing, and Indian patent-counsel review before external distribution or filing decisions.
