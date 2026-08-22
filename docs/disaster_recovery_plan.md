# DriftGuard-X Disaster Recovery Plan

This document outlines the testing procedures and response actions for catastrophic failures in the DriftGuard-X production environment.

## DR Test Plan (Quarterly)

1. **Simulate Database Corruption**
   - Drop a critical table in a staging environment.
   - Verify the `RecoveryFailureRate` alert triggers.
   - Execute Point-in-Time Recovery (PITR) using the PostgreSQL WAL archives.
   - Run the migration job to ensure schema integrity.
   - Validate that `ReplayStateManifest` records are intact.

2. **Simulate Cryptographic Key Compromise**
   - Rotate the Ed25519 signing keys used for the `RecoveryEligibilityCertificate`.
   - Verify that old, signed capsules fail validation and trigger the `CertificateVerificationFailures` alert.
   - Re-sign known-good manifests with the new keys.

3. **Simulate Total Cluster Loss**
   - Spin up a completely blank Kubernetes cluster.
   - Restore secrets from the secure vault.
   - Apply network policies and StatefulSets.
   - Restore database from off-site S3 backups.
   - Deploy API and Worker workloads.
   - Execute end-to-end synthetic checks to verify full operational capability.

## Runbooks for Alerts

### Alert: ReplayBudgetExhausted
**Trigger**: The BCRB scheduler is rejecting interventions due to budget limits.
**Action**:
1. Check the `dgx_replay_budget_exhaustion_total` metric to identify the tenant.
2. If the exhaustion is legitimate (e.g., massive traffic spike), temporarily increase the `MAX_REPLAYS` limit via dynamic configuration.
3. If caused by a runaway loop, quarantine the offending component version.

### Alert: HighReplayFailureRate
**Trigger**: Replay jobs are crashing or timing out consistently.
**Action**:
1. Check Worker pod logs for OOMKills or timeout exceptions.
2. Verify Redis connectivity.
3. Review if a recent config patch introduced a syntax error in the replay sandboxes.
