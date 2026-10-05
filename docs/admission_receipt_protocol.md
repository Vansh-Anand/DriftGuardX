# Admission Receipt Protocol V1

## Purpose

The admission receipt is a single-use authorization for one replay or recovery execution. It
binds the work request to the state, policy, evidence authority, resource estimate, rollback
reserve, and time window approved by the coordinator. A worker must verify these bindings before
creating an execution sandbox or invoking an external adapter.

The canonical implementation is `AdmissionReceiptV1` in
`packages/replay/src/admission_receipt.py`. `ReplayAdmissionReceipt` remains a compatibility alias.

## Immutable signed payload

The V1 signature covers the deterministic JSON encoding of:

- receipt identity: `receipt_id`, `schema_version`, `tenant_id`, `workload_id`, `run_id`, `nonce`;
- state: manifest, trace root, intervention, current version, candidate version, and capsule hashes;
- authority: policy hash/version, approval ID, evidence ceiling, and issuer identity;
- resources: predicted cost, uncertainty margin, rollback reserve, and resource pool ID;
- time: issue and expiry timestamps normalized to UTC with microsecond precision;
- cryptographic routing: key ID and signature algorithm.

JSON object keys are sorted, separators contain no optional whitespace, non-ASCII characters are
escaped, and the byte representation is prefixed by the domain
`DGX-REPLAY-ADMISSION-SIGNATURE-V1\0`. The signature value itself and mutable lifecycle fields are
not included in the signed payload.

The binding hash uses the same canonical payload with a separate
`DGX-REPLAY-ADMISSION-V1\0` domain. Domain separation prevents a signature or digest generated for
another DriftGuardX object from being interpreted as a receipt authorization.

## Lifecycle

```text
ISSUED -> VERIFIED -> CONSUMED
   |          |
   |          +----> VOIDED
   +----> RELEASED
   +----> VOIDED
   +----> EXPIRED
```

`CONSUMED`, `RELEASED`, `VOIDED`, and `EXPIRED` are terminal. One successful transition must win
under concurrent access. A refusal against a receipt already claimed by a legitimate worker must
not cancel that worker's claim.

## Worker verification order

The production verifier must fail closed in this order:

1. Load the receipt from authoritative storage.
2. Validate schema version and canonical encoding.
3. Resolve the trusted key by `key_id` and verify the issuer signature.
4. Check tenant/workload ownership and receipt lifecycle status.
5. Check expiry using an authoritative UTC clock.
6. Recompute manifest, trace, intervention, version, capsule, and policy bindings.
7. Enforce the admitted evidence ceiling.
8. Confirm the durable resource reservation remains active.
9. Atomically claim the receipt as `VERIFIED`.
10. Allocate execution resources only after the claim succeeds.

After execution, the worker constructs an `ExecutionAttestationV1` binding the receipt and its
binding hash to the tenant, worker identity, manifest, policy, runtime version, image digest,
execution interval, and outcome hash. The attestation is signed with a distinct worker key and
persisted while the receipt remains `VERIFIED`; only then may the receipt become `CONSUMED`.

SQLite provides the local/reference lifecycle store. Production mode selects the PostgreSQL
authority, which locks the resource-pool row before admission, reserves predicted cost plus
uncertainty and rollback capacity atomically, locks the receipt during worker claim, and releases
or charges the reservation in the same transaction as its terminal transition.

The migration creating `admission_resource_pools`, `admission_receipts`, and
`admission_audit_events` is revision `4a7c2f9d1e30`. `DGX_ADMISSION_STORE_BACKEND=postgres`
selects this backend explicitly; production mode selects it by default.

## Compatibility and rollout

Unsigned legacy receipts remain constructible during local migration. Production mode requires
signing configuration and refuses unsigned, invalid, or untrusted receipts before binding checks
or worker allocation. `DGX_ADMISSION_TRUSTED_KEYS_JSON` maps key IDs to trusted Ed25519 public
keys. No implicit fallback from signed to unsigned verification is permitted.

The environment-backed raw Ed25519 private key is a controlled-deployment bridge, not final key
custody. A production deployment should inject a `SignerProtocol` implementation backed by KMS or
HSM and retain only public verification keys in worker environments.
