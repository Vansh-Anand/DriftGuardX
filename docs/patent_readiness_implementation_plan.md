# DriftGuardX Patent-Readiness Implementation Plan

## Purpose

Strengthen the implementation and evidence for a focused, systems-level invention:

> A distributed, worker-enforced authorization protocol that validates a signed, state-bound, time-bounded, single-use receipt before allocating resources for replay or recovery.

This is an engineering plan, not legal advice. Do not publish new protocol details, benchmark results, or implementation changes without first confirming the disclosure strategy with qualified patent counsel. Public disclosures already made must be preserved, not rewritten or removed.

## Implementation Status

Completed:

- [x] Added the versioned `AdmissionReceiptV1` canonical contract.
- [x] Preserved `ReplayAdmissionReceipt` as a compatibility alias.
- [x] Added schema version, nonce, workload/run, policy, approval, resource-pool, issuer, and signing metadata.
- [x] Added deterministic canonical bytes with UTC timestamp normalization and domain separation.
- [x] Added Ed25519 signing and independent signature verification primitives.
- [x] Added explicit `EXPIRED` status and terminal-reason vocabulary.
- [x] Removed permissive string coercion from binding verification.
- [x] Added the V1 protocol and signature-coverage specification.
- [x] Added unit and integration coverage for canonicalization, signing, tampering, expiry, concurrency, restart, evidence ceilings, replay, and recovery compatibility.
- [x] Added trusted key resolution and fail-closed signature enforcement in production mode.
- [x] Bound workload, run, and resource-pool identity at API and worker boundaries.
- [x] Added a Postgres-backed authoritative receipt and resource-reservation store.
- [x] Added transactional pool locking, atomic receipt claim, and atomic reservation settlement.
- [x] Added ORM models and a reversible Alembic migration with metadata-parity validation.
- [x] Added a service-backed four-process PostgreSQL claim test for CI.
- [x] Added signed worker execution attestations covering runtime, image, policy, and outcome.
- [x] Required attestation persistence before a verified receipt can be consumed by the worker.

Next implementation increment:

- [ ] Export receipt-attestation audit links through the external certificate ledger.
- [ ] Replace the controlled environment-key signer with a KMS/HSM-backed provider.
- [ ] Add crash injection after verification and prove safe lease/recovery behavior.

## Scope

### In scope

- Durable, shared replay and recovery admission receipts.
- Worker-side signature and state validation before resource allocation.
- Atomic receipt lifecycle and distributed resource reservation.
- Worker execution attestations and audit linkage.
- Recovery execution governed by the same receipt protocol.
- Concurrency, crash-recovery, tamper, and policy/evidence-boundary tests.
- Reproducible multi-worker deployment and technical evidence.

### Out of scope

- New causal-diagnosis algorithms, GAT training, or bandit claims.
- Dashboard redesigns or mock UI work.
- Broad claims covering all AI drift detection, causal RCA, RAG replay, or governance.
- Deleting or rewriting Git history, licenses, contributors, or public artifacts.
- Representing this plan as a legal opinion or patentability guarantee.

## Invention Boundary

The implementation must make this technical behavior true:

1. The coordinator creates an authorization receipt before dispatching replay or recovery work.
2. The receipt binds the exact executable state, policy, evidence authority, resource reservation, and rollback conditions.
3. A worker independently reloads and recomputes those bindings from persisted authoritative state.
4. The worker refuses execution before allocating work if any binding, signature, status, expiry, tenant, or policy constraint fails.
5. Only one worker may consume a receipt, and its final lifecycle outcome is durably recorded.
6. Recovery actions obey the same receipt and rollback constraints as replay actions.

## Canonical Receipt Contract

Create one versioned, canonical receipt schema. Remove duplicated receipt/replay representations where practical; if compatibility requires duplicates temporarily, add explicit translation tests.

Required immutable fields:

| Group | Fields |
| --- | --- |
| Identity | `receipt_id`, `schema_version`, `tenant_id`, `workload_id`, `run_id`, `nonce` |
| State binding | `replay_manifest_hash`, `trace_root_hash`, `current_version_hash`, `candidate_version_hash`, `intervention_hash`, `recovery_capsule_hash` |
| Authority binding | `policy_hash`, `policy_version`, `approval_id`, `evidence_class_ceiling` |
| Resource binding | `predicted_cost_usd`, `cost_uncertainty_usd`, `rollback_reserve_usd`, `resource_pool_id` |
| Time binding | `issued_at`, `expires_at` |
| Cryptography | `key_id`, `signature_algorithm`, `payload_signature` |
| Lifecycle | `status`, `issued_by`, `consumed_by_worker_id`, `consumed_at`, `terminal_reason` |

Canonicalize the signed payload deterministically. Exclude mutable lifecycle fields from the issuer signature or use a distinct signed execution-attestation payload. Document precisely which fields are covered by each signature.

## Receipt State Machine

```text
DRAFT -> ISSUED -> VERIFIED -> CONSUMED -> RELEASED
                    |             |
                    |             -> VOIDED
                    -> VOIDED
ISSUED -> EXPIRED
```

Rules:

- Only `ISSUED` receipts can be verified.
- Only `VERIFIED` receipts can be consumed.
- Consumption is atomic and single-use.
- Expired, invalid, mismatched, or policy-incompatible receipts must become `VOIDED` or `EXPIRED` and must never execute.
- Terminal transitions are immutable and produce an audit event.
- A worker crash must not permit a second worker to consume the same receipt.

## Delivery Plan

### Milestone 0: IP evidence preservation

**Goal:** create a clean factual record without altering repository history.

Tasks:

- Export commit metadata, authors, timestamps, tags, and branch heads.
- Record repository visibility, public release dates, and license history.
- Create an inventor-contribution matrix for receipt issuance, worker validation, evidence ceiling, rollback reserve, and terminal accounting.
- Collect dated design notes, test output, architecture diagrams, and benchmark artifacts.
- Create a counsel question list covering public disclosure, prior license terms, assignments, and inventor contributions.

Acceptance criteria:

- Evidence archive has hashes and dates.
- No historical files, commits, or licenses are modified.
- Every patent-relevant feature has an identified conception source or an explicitly unresolved owner.

### Milestone 1: Canonical schema and protocol specification — implemented

**Goal:** make the receipt protocol unambiguous and testable.

Primary code areas:

- `packages/replay/src/admission_receipt.py`
- `packages/replay/src/admission_store.py`
- `packages/contracts/src/models.py`
- `packages/contracts/src/recovery_models.py`
- `packages/recovery/src/executor.py`

Tasks:

- Define `AdmissionReceiptV1` as the canonical contract.
- Define deterministic serialization and hashing.
- Define receipt state transitions and terminal reasons as enums.
- Specify verification ordering: schema -> signature -> tenant -> expiry -> status -> manifest/state bindings -> policy/evidence -> resource availability -> atomic consumption.
- Add a protocol document with sequence and state-machine diagrams.

Acceptance criteria:

- One documented canonical payload is signed and verified identically by API and worker code.
- Unit tests reject semantically identical payloads encoded non-canonically when signature verification would otherwise be ambiguous.
- Compatibility adapters have explicit tests.

### Milestone 2: Shared authoritative store and atomic reservation

**Goal:** replace local-only assumptions with correct multi-worker behavior.

Primary code areas:

- `packages/replay/src/admission_store.py`
- database migrations and persistence models
- `apps/api/src/routes/runs.py`
- `apps/worker/src/worker.py`

Tasks:

- Implement a Postgres-backed admission store as the production implementation.
- Store receipts, receipt events, reservations, resource-pool balances, and execution attestations durably.
- Use transactions plus row locks or optimistic concurrency with compare-and-swap semantics.
- Enforce an idempotency key for issuance.
- Atomically reserve predicted cost plus rollback reserve before receipt issuance.
- Atomically consume or release a reservation during terminal transitions.
- Keep SQLite only as a clearly labeled local-development implementation.

Acceptance criteria:

- Two or more workers racing for one receipt produce exactly one successful consumption.
- Aggregate active reservations never exceed `pool_budget - required_rollback_reserve`.
- Restarting API or worker processes does not lose active receipt state.
- Repeating an issue request with the same idempotency key does not create a second reservation.

### Milestone 3: Cryptographic issuance and worker attestation

**Goal:** make authorization and execution provenance tamper-evident.

Primary code areas:

- `packages/replay/src/admission_receipt.py`
- `packages/ledger/`
- `packages/recovery/src/executor.py`
- worker configuration and secrets abstraction

Tasks:

- Sign immutable receipt payloads with a named key and algorithm.
- Implement key rotation using `key_id`; do not embed private keys in code or repository configuration.
- Add a KMS-compatible signing abstraction; a local test signer may exist only for development/testing.
- Require worker-side signature verification before any allocation or sandbox start.
- Emit a signed `ExecutionAttestation` containing receipt hash, manifest hash, policy hash, worker/image version, timestamps, outcome hash, and terminal reason.
- Link receipt, attestation, and recovery outcome to the existing append-only ledger.

Acceptance criteria:

- Any modification to signed immutable fields causes refusal before execution.
- Unknown, revoked, or expired signing keys cause refusal in production mode.
- Attestations are verifiable independently from the worker process.
- Ledger event order links issuance, verification, consumption, outcome, and release/void.

### Milestone 4: Worker-side fail-closed enforcement

**Goal:** prove that unsafe jobs cannot reach execution.

Primary code areas:

- `apps/worker/src/worker.py`
- `packages/replay/`
- `packages/recovery/src/executor.py`
- replay sandbox/engine integrations

Tasks:

- Move the authorization gate directly in front of sandbox creation, provider call, or recovery adapter invocation.
- Independently recompute every bound hash from persisted state.
- Refuse: missing receipt, bad signature, tenant mismatch, expired receipt, reused receipt, state/version drift, policy mismatch, insufficient reserve, or evidence ceiling violation.
- Ensure replay and recovery use the same verifier instead of parallel bypass paths.
- Return structured, reason-coded refusals without leaking cross-tenant details.

Acceptance criteria:

- No sandbox, provider request, or recovery adapter invocation occurs before successful verification.
- Every refusal has a durable audit record and stable reason code.
- Legacy execution paths are removed, redirected through the verifier, or explicitly disabled in production.

### Milestone 5: Recovery and rollback integration

**Goal:** ensure remediation cannot bypass the authorization model.

Primary code areas:

- `packages/recovery/src/executor.py`
- `packages/recovery/`
- policy and approval services

Tasks:

- Bind recovery capsule hash, required approval identity, policy version, and rollback plan to the receipt.
- Require an active verified receipt for recovery start, continuation, rollback, and release.
- Model partial success and worker crash recovery explicitly.
- Permit rollback only where the receipt/policy authorizes it.
- Record recovery action idempotency and causal linkage.

Acceptance criteria:

- A recovery action cannot execute with a receipt issued for a different replay/run/version.
- A partial recovery produces a durable, auditable terminal state and only authorized rollback.
- Repeated recovery requests are idempotent.

### Milestone 6: Patent-quality validation suite

**Goal:** generate credible technical evidence of the protocol's effect.

Create integration tests and a reproducible benchmark harness for the following scenarios:

| Scenario | Required result |
| --- | --- |
| Concurrent consumption | Exactly one worker executes |
| Worker crash/restart | No duplicate execution after restart |
| Receipt expiry | Refusal occurs before allocation |
| Manifest/trace/version drift | Refusal occurs before allocation |
| Policy mismatch | Refusal occurs before allocation |
| Signature tampering | Refusal occurs before allocation |
| Evidence escalation | Higher authority cannot be fabricated |
| Budget contention | Reservations never oversubscribe the pool |
| Cross-tenant reuse | Receipt is rejected |
| Partial recovery failure | Only authorized rollback occurs |
| Baseline comparison | Generic job token/queue fails cases the protocol prevents |

Collect these metrics:

- number and percentage of unsafe requests refused before execution;
- duplicate executions prevented;
- resource/budget overruns prevented;
- verification latency and throughput overhead;
- crash-recovery correctness;
- audit-chain completeness;
- false refusals and reason-code distribution.

Acceptance criteria:

- Tests run reproducibly in CI against Postgres and multiple worker processes.
- Raw data and fixed configuration are preserved with checksums.
- Reports distinguish simulation, controlled replay, and production-canary evidence.
- Do not claim scheduler superiority unless a preregistered, fair baseline experiment proves it.

### Milestone 7: Deployment and observability

**Goal:** demonstrate a credible distributed reference deployment.

Tasks:

- Add a Docker Compose environment with API, Postgres, Redis, at least two workers, signer abstraction, and observability stack.
- Add a controlled Kubernetes deployment if the project already supports it.
- Add metrics: issued, verified, rejected, consumed, released, voided, expired, signature failures, mismatches, evidence ceiling violations, and reservation conflicts.
- Add dashboards/alerts only after the metrics are trustworthy; UI work is secondary.

Acceptance criteria:

- A documented command sequence runs contention, crash, and tamper tests in the reference environment.
- Operator can trace an execution from receipt issuance to final attestation/ledger record.
- Production configuration refuses mock authentication, mock signing, and local-only stores.

### Milestone 8: Filing package preparation

**Goal:** produce materials that a patent professional can evaluate without reverse-engineering the repository.

Prepare:

- focused invention disclosure;
- architecture, state-machine, and sequence diagrams;
- canonical receipt schema and signature coverage table;
- failure-mode and security-boundary table;
- reproducible test report and raw evidence index;
- prior-art comparison table;
- inventor contribution matrix;
- public-disclosure and license timeline;
- proposed independent method/system/computer-readable-medium claims;
- dependent claim candidates for signatures, expiry, evidence ceilings, resource reservation, atomic transitions, worker attestation, and recovery binding.

## Claim Direction

The independent claim should describe the worker-side enforcement mechanism, not a generic AI monitoring platform.

Avoid making the following the independent invention:

- causal graph diagnosis;
- RAG replay by itself;
- bandit scheduling;
- uncertainty metrics;
- dashboards;
- generic approval workflows;
- generic hash chains.

Those may remain useful dependent features or product context.

## Required Quality Gates

- `ruff`, type checks, and full test suite pass.
- Multi-worker Postgres integration tests pass in CI.
- Security tests show fail-closed behavior for every authorization failure.
- No private key, token, or sensitive evidence is committed.
- API and worker use the same canonical receipt verifier.
- Documentation explicitly separates implemented behavior from prototype/simulated behavior.
- New patentable details remain non-public until disclosure strategy is approved.

## Definition of Done

The work is ready for a stronger patent filing review when:

1. A worker cannot execute replay or recovery without a valid, state-bound, signed receipt.
2. Receipt single-use, expiry, tenant isolation, policy/evidence limits, resource reserve, and rollback conditions are enforced under multi-worker contention.
3. The worker produces independently verifiable execution attestations.
4. Tests prove refusal happens before resource allocation or external side effects.
5. The evidence package is reproducible, dated, and technically precise.
6. Inventorship, assignments, disclosure history, and license history have been reviewed by qualified counsel.
