# Candidate Technical Claim Outline

Target: India. Status: engineering draft for registered patent-agent review.
This replaces the earlier USPTO-style outline, whose broad claims exceeded the
verified implementation. It is not a completed Form 2 or a patentability opinion.
Read patent_claims_audit.md and prior_art_worksheet.md with this outline.

## Candidate system combination

### State-bound admission control embodiment

A computer-implemented technical system for controlling autonomous recovery
operations in an instrumented computing pipeline, comprising:

1. A durable receipt store configured to persist, before dispatch, a canonical
   admission record binding a tenant identifier, a replay-state manifest digest, a
   trace-root digest, an intervention identity digest, a current component version,
   a candidate component version, a policy-state digest, a rollback-capsule digest,
   a bounded resource reservation, an evidence ceiling, and an expiry interval.
2. An admission coordinator configured to atomically reserve the bounded resource
   amount and append an issue event to an append-only receipt event sequence.
3. A worker or recovery executor configured to recompute the bound values from the
   state records available at the worker boundary, atomically claim the receipt, and
   refuse dispatch before allocating the replay or remediation process when a bound
   value, expiry interval, receipt status, or evidence class does not match.
4. A terminal transition controller configured to consume the reservation once on
   successful completion, or release and void it on refusal, timeout, expiry, or
   failed execution, while appending a hash-linked event identifying the transition.

The technical contribution should be argued as distributed state and resource
control: it prevents a stale recovery operation from crossing a time-of-check to
time-of-use boundary and bounds capacity consumed by refused or failed operations.

### Candidate method claim

A computer-implemented method for state-bound admission control of an autonomous
recovery operation, comprising issuing and durably storing the canonical receipt,
reserving predicted resource cost plus uncertainty and rollback reserve, recomputing
the receipt bindings at a worker or executor boundary, atomically changing the
receipt from issued to verified only when the bindings and expiry are valid, refusing
the operation before execution on mismatch or evidence promotion, and atomically
consuming or releasing the reservation while appending the corresponding event.

These are engineering claim candidates for Indian patent-agent review, not legal
claims or a patentability conclusion.

A computer system configured to evaluate a proposed recovery for an instrumented
computing pipeline, comprising:

1. A trace and state store holding execution records and a replay manifest identifying
   input state and component versions.
2. A replay controller refusing execution when required pinned state is unavailable,
   selecting candidates subject to predicted cost, measured cost uncertainty, remaining
   budget and a configured rollback reserve.
3. A worker executing an admitted candidate in a killable process boundary, enforcing
   elapsed-time and serialized-output limits, with platform-dependent memory enforcement.
4. An evidence evaluator retaining the origin of replay outcomes and producing
   assumption-qualified statistical results, including an unsupported result when
   required numerical conditions fail.
5. A recovery gate evaluating evidence and tenant-bound authorization before an action,
   with integrity verification of relevant recovery records and retained audit evidence.

This is a candidate combination, not an assertion that every deployment connects all
five components or that the combination distinguishes the cited prior art. The
source/test chart identifies which pieces have been demonstrated. Integration into
the exact claimed sequence must be traced and tested before final claim selection.

## Candidate dependent elements

- Refusal of a replay when a required manifest or component version cannot be resolved,
  instead of executing a different version.
- Admission based on predicted resource cost plus a cost-uncertainty margin being at
  most remaining budget minus a reserved rollback allowance.
- Incremental collection of bounded serialized result frames with termination on
  execution timeout.
- Explicit separation of synthetic, controlled replay, and production canary evidence.
- A rollback record whose integrity digest covers tenant, component, prior and target
  state, artifact hashes, compatibility constraints, rollback parameters, verification
  steps, author and validity interval; rejecting changed execution conditions before use.
- A conformal result using the one-based residual order statistic at
  ceil((n+1)*confidence), returning unsupported when no finite rank is available.
  This is a standard method included for implementation specificity, not novelty.

## Scope not supported by this prototype

Do not claim hardware quarantine, kernel audit hooks, absolute sandbox security,
GAT outputs proving causation, durable distributed VTI transactions, general
scheduler superiority, independently verified production safety, or automatic proof
that calibration samples are independent. The VTI coordinator is an in-memory
simulation; the capsule seal is an integrity digest, not a signature or protection
against an attacker controlling both the data and stored digest.

GAT layers, a web dashboard, policy levels, generic cryptographic signatures, and
UCB scheduling do not establish an inventive step merely by appearing together.
The Indian patent agent should assess the claimed technical contribution under the
applicable CRI framework and choose claim form and scope.
