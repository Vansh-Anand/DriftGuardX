# Novelty Strategy and Technical Differentiation

Prepared: 2026-09-08. Target jurisdiction: India. This is an engineering and
research plan, not a patentability opinion or clearance search.

## Current novelty position

The present prototype contains useful engineering controls, but the broad idea is
crowded. Existing material covers counterfactual root-cause analysis with isolated
replay repair, budgeted exploration, graph attention, conformal uncertainty,
cryptographic software provenance, integrity-driven containment and replay/rollback.
See `prior_art_worksheet.md`, especially P1, P6 and P7.

The current benchmark also does not support a scheduler-superiority assertion: the
neutral BCRB ordering matched fixed ordering, and the oracle configuration receives the
injected fault label. It cannot be presented as autonomous diagnosis or online-learning
evidence.

## What not to claim as novel

- A provenance log, hash, signature, rollback record or generic certificate.
- Counterfactual diagnosis followed by isolated replay or repair.
- A bandit with a budget or a static rollback reserve.
- Graph attention, conformal prediction or a dashboard.
- Merely grouping the above components in one product.

Those elements may be useful implementation detail. They do not, from this review,
provide a defensible inventive-step story on their own.

## Recommended next embodiment

Build a state-bound replay-admission receipt with a two-phase lifecycle:

1. **Prepare and reserve.** A coordinator canonicalizes and hashes the replay manifest,
   trace root, intervention's current and candidate versions, tenant/policy version,
   predicted charge plus uncertainty margin, rollback reserve, evidence ceiling,
   capsule integrity hash and expiry. It stores one durable reservation keyed by that
   digest before dispatch.
2. **Verify and execute.** The worker independently recomputes the digest and refuses
   execution before resource allocation if any bound input differs. It reports a
   terminal outcome against that reservation only.
3. **Verify and recover.** The recovery gate verifies the same receipt, capsule and
   evidence ceiling. It rejects expired receipts, a changed target, mismatched policy or
   an attempt to promote simulated or controlled evidence to production authority.
4. **Finalize.** Completion consumes the reservation once; failed, timed-out and expired
   receipts void it and release the reserved capacity. Replays cannot be retried with a
   stale receipt.

This is more specific than a generic signed envelope: the proposed technical effect is
preventing time-of-check/time-of-use drift across distributed admission, execution and
recovery decisions while preserving the rollback capacity used in the admission
decision. It is not currently implemented, and may still be anticipated or obvious.

## Validation required before claiming it

- Implement a durable, transactional reservation state machine with idempotency keys.
- Pass the receipt through the actual replay worker boundary; do not verify only in the
  API process.
- Add tests that independently mutate every bound field and prove refusal before work is
  allocated, including concurrent double-finalization and expiry races.
- Meter actual resources and prove reservation release/consumption is correct after
  timeout, worker loss and retry.
- Add an external-state adapter that attests the referenced dataset/index/configuration
  snapshot, rather than relying solely on application-supplied identifiers.
- Produce a claim chart against P1, P6, P7, R1 and R5, including the closest independent
  claims and a motivation-to-combine analysis by a patent professional.

## Research route for scheduler novelty

If the project seeks a separate algorithmic contribution, train a fault-signature to
prior model using only data available before intervention, evaluate on held-out fault
families and compare against fixed, random, uniform-prior and an oracle upper bound.
Use real worker outcomes or a clearly delimited simulator, report query-family grouped
confidence intervals, and pre-register the allocation and stopping rules. Do not use
the injected answer in any non-oracle condition.

This is substantial research work. Until it produces a reproducible, leakage-free
advantage, the scheduler should be described as a safety-aware heuristic, not an
inventive performance result.

## India framing

For an India filing, the disclosure should center on the measurable computer-system
effect: preventing dispatch and state change when a distributed replay's pinned state,
reserved capacity or evidence authority has drifted. It should explain the data
structures, canonicalization, state transitions, refusal paths and measured resource
behavior. The patent agent must assess the result under the current Computer Related
Inventions guidance and Section 3(k), and determine whether the technical contribution
is enough to avoid a "computer programme per se" or algorithm objection.

Before filing, supply the human inventors, applicant/ownership, any filing or priority
history, and the earliest public disclosure date. Preserve dated design records and do
not rely on Git timestamps as a priority claim.
