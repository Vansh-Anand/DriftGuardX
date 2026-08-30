# DriftGuard-X Invention Disclosure (Engineering Draft)

Status: confidential engineering record; counsel review required. This document identifies candidate inventive concepts and their implemented support. It does not conclude novelty, non-obviousness, freedom to operate, inventorship, or patentability.

## Technical problem

Agentic and retrieval-augmented systems are stochastic, stateful, and assembled from independently versioned components. A recovery decision can therefore be unsafe when it is based on correlation, an incompletely reproduced execution state, an unbounded replay, or an approval that is not cryptographically tied to the tested intervention.

## Candidate inventive combination

The implemented candidate combines these operations into one fail-closed recovery protocol:

1. Bind the original trace, versioned component state, exogenous controls, intervention, resource budget, and evidence class into canonical hashed records.
2. Admit counterfactual experiments before allocation using expected information gain, measured cost history, uncertainty, remaining budget, and rollback reserve.
3. Execute admitted work behind a killable process or container boundary while incrementally enforcing wall-time, resident-memory, and serialized-output limits.
4. Reject recovery unless at least one replay passes divergence validation and the stopping outcome is evidentially confirmed.
5. Require an authenticated, unexpired, tenant-bound access context at the recovery validation boundary.
6. Bind policy, approvals, canary outcome, capsule hash, executor image digest, and evidence provenance into an Ed25519-signed recovery eligibility certificate and tamper-evident ledger record.

The candidate distinction is the protocol-level coupling of pre-allocation resource admission, controlled causal replay, evidence sufficiency, tenant authorization, and cryptographic recovery binding—not any isolated use of containers, bandits, causal graphs, signatures, or audit ledgers.

## Implemented support

| Mechanism | Principal implementation |
|---|---|
| Tenant-derived API authorization | `apps/api/src/dependencies.py`, `apps/api/src/routes/`, `tests/security/test_route_tenant_enforcement.py` |
| Killable replay and incremental limits | `packages/replay/src/engine.py`, `packages/replay/src/sandbox.py` |
| Resource reservation and reconciliation | `packages/contracts/src/interfaces.py`, `packages/replay/src/causal_experiment_planner.py`, `packages/recovery/src/orchestrator.py` |
| Divergence and evidentiary fail-closed gate | `packages/recovery/src/orchestrator.py`, `packages/replay/src/stopping_rule.py` |
| Evidence provenance taxonomy | `packages/contracts/src/evidence.py`, `packages/ledger/src/schema.py`, `packages/ledger/src/export.py` |
| Certificate canonicalization/signing | `packages/contracts/src/models.py`, `packages/ledger/src/crypto.py`, `packages/recovery/src/engine.py` |
| Reproducibility binding | `uv.lock`, `requirements.lock`, `scripts/generate_experiment_manifest.py` |

## Candidate claim directions for counsel

- A computer-implemented recovery method requiring the ordered combination of resource admission, bounded replay, validated causal divergence, evidentiary stopping, tenant authorization, and cryptographically bound recovery eligibility.
- A replay executor that enforces memory and output limits incrementally across a killable boundary before parent-process materialization, with the measured result reconciled against a prior resource reservation.
- An evidence certificate and ledger schema that makes evidence provenance (synthetic simulation, controlled replay, or production canary) part of the signed/hash-bound recovery decision.
- A fail-closed state machine that prevents a high-confidence prior from authorizing recovery until replay-derived evidence has passed divergence validation.

## Evidence boundaries and known gaps

- Current benchmark evidence is controlled synthetic or mocked-integration evidence, not production replay evidence.
- Container isolation tests require a live Docker daemon; process-boundary tests run without Docker.
- KMS/HSM signing remains an integration boundary; local tests use ephemeral development Ed25519 keys.
- The repository does not itself establish novelty over prior art. A professional search should examine causal debugging, delta debugging, counterfactual execution, multi-armed bandit experiment selection, sandbox resource enforcement, signed software attestations, and automated rollback/recovery certificates.

## Inventorship and disclosure record to complete

Record each contributor's conception date and specific contribution, supporting notebooks/issues/commits, first disclosure outside the confidential team, first public use or offer for sale, and any funding or employment-assignment obligations. Preserve the content-addressed experiment manifests and signed release tags used to support technical-effect statements.
