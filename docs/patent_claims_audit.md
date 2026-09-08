# Claim Support Audit

Updated 2026-09-08. Engineering support, not a novelty or filing-readiness conclusion.
The preceding audit included a nonexistent feature module and overstated several
test scopes. This chart supersedes it.

| Candidate element | Source | Relevant tests | Demonstrated scope |
|---|---|---|---|
| Manifest refusal and content identity | packages/replay/src/engine.py; packages/contracts/src/models.py | tests/unit/test_manifest.py; tests/unit/test_manifest_integrity.py; tests/unit/test_api_replay_manifest.py | Refusal/hash/ownership checks under fixtures; not full production state capture |
| Resource admission and reserve | packages/replay/src/bandit.py | tests/unit/test_bcrb_orchestrator.py; tests/unit/test_controlled_replay_benchmark.py | Controller tests and labelled retrieval ablations; not autonomous diagnostic superiority |
| Process limits and bounded output | packages/replay/src/sandbox.py; packages/replay/src/engine.py | tests/unit/test_sandbox.py; tests/e2e/test_container_sandbox.py | Restricted process behavior; container tests depend on environment |
| Numerical statistical guards | packages/evaluation/src/bounds.py | tests/unit/test_bounds.py; tests/e2e/test_bounds_calibration.py | Finite inputs, conformal rank and refusal, downstream rejection of invalid evidence |
| Policy and approvals | packages/policy/src/resolver.py; packages/policy/src/approvals.py | tests/security/test_policy_security.py; tests/integration/test_security_audit.py | Tenant/policy/approval fixtures; no claim of certified live operations |
| Capsule execution-condition seal | packages/recovery/src/capsule.py | tests/unit/test_capsule_integrity.py; tests/e2e/test_recovery.py | Detects changes to hashed fields including nested compatibility constraints |
| Signature and chain verification | packages/ledger/src/crypto.py; packages/ledger/src/chain.py | tests/security/test_evidence_integrity.py; tests/e2e/test_ledger_tamper.py | Signature/content tamper tests; not external witness or production KMS certification |
| Evidence provenance | packages/contracts/src/evidence.py; packages/replay/src/engine.py | tests/unit/test_replay_provenance.py | Synthetic/controlled distinctions in tested paths |
| Benchmark artifact consistency | scripts/verify_controlled_evidence.py | tests/unit/test_controlled_replay_benchmark.py | Digest, prior-label, count and pairing consistency; not independent authenticity |

## Optional prototype elements

- GAT implementation: packages/detectors/src/gat_inference.py and
  tests/integration/test_gat_api.py. Checkpoint compatibility tests do not measure
  predictive accuracy. Operation-name encoding currently uses Python hash(), so
  cross-process deterministic encoding is not established. GAT is not essential
  to the revised claim outline.
- ARC: packages/replay/src/arc_isolator.py and tests/e2e/test_arc_isolator.py.
  This is monkey-patching with synthetic loopback and an in-memory quarantine.
- VTI: packages/replay/src/vti_coordinator.py and tests/e2e/test_vti_2pc.py.
  This is simulated staging with prefix-based clearance; it is not durable
  distributed atomic commit or cryptographic recovery authorization.

## Exclusions and migration notes

Independent bounded samples and calibration separation are caller obligations,
not facts discoverable from numerical arrays. A supported bound is not proof of
causation. Capsule integrity is not a signature, and an in-memory registry is not
a durable single-use capability service.

The capsule seal now covers additional execution fields. Capsules sealed using
the old field set must be recreated through the authorized creation path; do not
silently accept a legacy hash as protection for newly covered fields.

Tests listed here identify relevant behavior; passing them does not prove that
all candidate elements are connected in one deployed, independently validated
workflow. Hosted Linux/container and production gates remain external.
