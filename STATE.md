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

## Limits

Local experiments record a dirty working tree and exact implementation hashes;
they are not clean hosted-CI evidence or production canaries. Windows skips and
existing coroutine warnings remain recorded. No new production deployment,
container security assessment, KMS integration, patent filing or grant was verified.
Prior statements that the entire project was complete were too broad.
