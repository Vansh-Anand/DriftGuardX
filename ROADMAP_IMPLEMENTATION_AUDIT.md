# Roadmap Implementation Audit: Removing Simulated/Fabricated Results

## Pre-Change Audit Findings

During our audit, we identified several areas where the repository was improperly fabricating success or hardcoding simulated utility within operational paths:

1. **`packages/replay/src/test_framework.py`**
   - **Previous logic:** `CanaryTestFramework.execute_canary` hardcoded `simulated_utility = 0.95`. `validate_quarantine` simply returned `True` for everything except "agent", fabricating quarantine confirmation.
   - **New logic:** `execute_canary` now explicitly returns `utility_observed=None`, removing the fabrication. `validate_quarantine` raises `NotImplementedError` preventing it from being used to fake production validation.

2. **`apps/api/src/services/recovery_pipeline.py`**
   - **Previous logic:** `EndToEndRecoveryPipeline` falsely labeled the certificate evidence as `RecoveryEvidenceKind.CONTROLLED_REPLAY` when it was actually using `CanaryTestFramework`.
   - **New logic:** Explicitly labels the certificate with `RecoveryEvidenceKind.SYNTHETIC_SIMULATION` when generating the recovery certificate. It also gracefully handles the `NotImplementedError` from test frameworks.

3. **`packages/recovery/src/orchestrator.py`**
   - **Previous logic:** The `IncidentMachine` blindly transitioned from `CANARY` status directly to `RECOVERED` with the message "Canary successful. Recovery deployed." without actual verification.
   - **New logic:** The machine now transitions to `RECOVERY_REJECTED` with an explicit message: "Real canary deployments are currently blocked pending production support. Refusing to fabricate recovery success."

4. **`packages/policy/src/transfer_guard.py`**
   - **Previous logic:** `TransferGuard` only checked the cryptographic signature and similarity scores, but allowed synthetic simulations to be transferred across boundaries.
   - **New logic:** `ProvenanceEnvelope` now carries the `evidence_kind`. The guard explicitly rejects the transfer if `evidence_kind == RecoveryEvidenceKind.SYNTHETIC_SIMULATION`.

## Evidence Propagation Changes
- Extended `ProvenanceEnvelope` in `transfer_guard.py` to include `evidence_kind`.
- Ensured tests in `test_recovery_pipeline.py` assert that `evidence_kind` is correctly propagated as `SYNTHETIC_SIMULATION` when using the mock framework.
- Ensured `test_transfer_guard.py` correctly verifies that `SYNTHETIC_SIMULATION` is rejected.
