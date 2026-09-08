# Current State

Verified 2026-09-08. This file restores the canonical startup status previously
missing on main. See docs/ai/CONTEXT_INDEX.md for scoped navigation.

## Patent review work

Target jurisdiction is India. The current technical handoff is
docs/patent_evidence_package.md. A preliminary primary-source search found
substantial overlap with existing counterfactual replay repair and budgeted-bandit
work. Novelty, inventive step, eligibility and filing readiness are unresolved.
No application or priority date was supplied. Inventorship, ownership and earliest
public disclosure require applicant confirmation and Indian patent-agent review.

## Verified engineering evidence

- Full Python suite after bounds/benchmark fixes: 556 passed, 22 skipped, 7 warnings.
- After the subsequent capsule/verifier changes: focused suite 79 passed.
- Two SciFact controlled retrieval experiments: seeds 42 and 7, 30 eligible queries
  each, five strategies, four attempted fault families. Internal artifact hashes
  and protocol consistency verified by scripts/verify_controlled_evidence.py.
- Neutral BCRB equals fixed ordering in these runs. The one-replay oracle baseline
  receives ground truth. No autonomous scheduler superiority is established.
- Statistical bounds now reject invalid numeric data and unattainable finite
  conformal ranks. Capsule hashes now bind expiry and other execution conditions.
- Durable state-bound admission is implemented in
  `packages/replay/src/admission_store.py`. It persists receipts across process
  restarts, claims them atomically at `ISSUED -> VERIFIED`, consumes them once,
  and records hash-chained ISSUE, VERIFY, CONSUME, RELEASE, VOID, and
  MISMATCH_REFUSAL events.
- The replay API and replay worker verify tenant, manifest, trace-root,
  intervention, version, policy, capsule, expiry, and evidence-ceiling bindings
  before executor dispatch. The recovery executor exposes
  `execute_with_admission` for the same pre-capsule gate.
- New receipt tests cover stale version, changed policy, changed trace, expiry,
  evidence promotion, restart persistence, single-use claiming, and audit-chain
  continuity. Receipt, migration, and replay API verification: 25 passed.

## Limits

Local experiments record a dirty working tree and exact implementation hashes;
they are not clean hosted-CI evidence or production canaries. Windows skips and
existing coroutine warnings remain recorded. No new production deployment,
container security assessment, KMS integration, shared-host database deployment,
patent filing or grant was verified. The broader replay regression suite currently
has one unrelated failing assertion in
`tests/unit/test_replay_isolation.py::test_replay_improves_reliability_over_experimental`
(observed improvement `-0.2017`).
Prior statements that the entire project was complete were too broad.
