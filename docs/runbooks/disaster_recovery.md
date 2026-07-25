# Disaster Recovery Runbook

## Database Backup and Restore
### Backup (Postgres)
```bash
kubectl exec -it <postgres-pod> -- pg_dump -U postgres driftguard > backup.sql
```
### Restore (Postgres)
> [!WARNING]
> Restoring a database will overwrite the current ledger. This must only be done in a declared DR scenario.
```bash
cat backup.sql | kubectl exec -i <postgres-pod> -- psql -U postgres -d driftguard
```
### Verify Restore
Run the cryptographic verification script to ensure the restored ledger is valid:
```bash
python -m scripts.verify_ledger
```

## Key Rotation (KMS / Ed25519)
If the signing key is compromised:
1. Generate a new key in KMS or Vault.
2. Update the `driftguard-secrets` Kubernetes secret with the new key reference/ARN.
3. Restart the API deployment: `kubectl rollout restart deploy/driftguard-api`.
4. Run the key migration script to sign a rollover certificate.

## Object Store Backup
All ReplayCapsule JSONs must be continuously replicated to a cross-region bucket (e.g., AWS S3 Cross-Region Replication). No manual backups are required.
