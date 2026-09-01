# DriftGuard-X Architecture

## Purpose and claim boundary

DriftGuard-X is an evidence-oriented control plane for diagnosing and governing
recovery in agentic and retrieval-augmented systems. Its defensible architectural
unit is the closed chain from tenant-bound trace ingestion to isolated replay,
resource admission, policy authorization, and hash-bound recovery evidence.

The system does not treat correlation as causation. A candidate becomes eligible
for recovery only after an intervention is executed inside a replay boundary and
the observed outcome passes the configured evidentiary stopping and policy gates.

## Trust and execution planes

1. **Identity and tenancy plane.** FastAPI authenticates every non-public route.
   Tenant scope is derived from authenticated membership; tenant identifiers from
   request paths, queries, or bodies are never an authority source.
2. **Trace and state plane.** The Trace SDK records typed spans and immutable
   component, policy, prompt, corpus, model, and dependency identities. Ingestion
   validates run, pipeline, and tenant ownership before persistence.
3. **Causal diagnosis plane.** Trace topology, detector observations, graph
   diffusion, and belief updates rank root-cause candidates. These are hypotheses,
   not recovery proof.
4. **Counterfactual execution plane.** Replay manifests bind the original request,
   trace digest, exogenous inputs, component state, dependency lock, and execution
   artifact. Replays execute behind a killable process or container boundary.
5. **Resource-admission plane.** Wall time, resident memory, output bytes, replay
   count, and cost are accounted incrementally. Admission occurs before execution;
   output and memory limits are enforced before parent-process materialization.
6. **Recovery governance plane.** A strictly tightening policy hierarchy checks
   role, tenant, confidence, freshness, blast radius, action class, and evidence
   provenance. A replay result alone cannot authorize a state change.
7. **Evidence and ledger plane.** Certificates bind the recovery decision to the
   replay, intervention, tenant, issuer, evidence class, and result digest. Ledger
   exports keep synthetic simulation, controlled replay, and production canary
   evidence distinct.

## Closed-loop protocol

```text
authenticated trace
  -> tenant-scoped causal graph
  -> ranked hypotheses
  -> resource reservation
  -> isolated counterfactual replay
  -> measured outcome + belief update
  -> evidentiary stopping rule
  -> policy authorization
  -> recovery action
  -> signed/hash-chained certificate
```

The important invariant is monotonic evidence: no downstream stage may silently
upgrade an evidence class, weaken tenant scope, substitute unbound state, or turn
an unresolved replay into a confirmed recovery.

## Evidence classes

| Class | Permitted meaning | Prohibited claim |
|---|---|---|
| `synthetic_simulation` | Generated or mocked fault behavior | Real-system effectiveness |
| `controlled_replay` | Executed workload against a bound, non-production state snapshot | Production safety or live recovery |
| `production_canary` | Capability-gated canary in a declared production environment | Universal safety or causality |

The real-data SciFact path loads a hash-pinned public corpus, queries, and qrels;
executes deterministic BM25 retrieval; tombstones relevant index entries as a
controlled fault; replays candidate interventions; and binds every trial and the
complete manifest with SHA-256. It fails closed if data is missing or altered and
is classified only as `controlled_replay`.

## Deployment topology

- **Web console:** Next.js evidence and operations surface.
- **Control plane:** FastAPI, async PostgreSQL, OIDC, and tenant-scoped services.
- **Job plane:** ARQ/Redis worker for durable asynchronous work.
- **Replay plane:** local process isolation for development and a digest-pinned
  container execution boundary for promoted environments.
- **Evidence plane:** PostgreSQL records plus exported immutable manifests and
  cryptographic ledger artifacts.

Kubernetes manifests intentionally contain zero image-digest placeholders until
CI promotion replaces them with registry-produced immutable digests. A manifest
with a zero digest is non-deployable by design.

## Patent-oriented technical differentiators

The implementation record should focus on the combination and data bindings, not
on generic RAG monitoring or generic bandits in isolation:

1. tenant-bound replay-equivalence manifests coupling trace, exogenous state,
   dependency identity, execution artifact, and intervention;
2. sequential causal experiments jointly constrained by information gain,
   measured resource admission, blast radius, and rollback reserve;
3. evidence-class monotonicity carried through API schemas, UI, policy decisions,
   certificates, ledger exports, and benchmark manifests; and
4. recovery eligibility that requires both replay-observed mitigation and a
   capability-gated, freshness-bound authorization context.

These are engineering differentiators and candidate claim material. Novelty,
inventive step, sufficiency, and Indian computer-related-invention eligibility
still require a prior-art search and qualified patent counsel.
