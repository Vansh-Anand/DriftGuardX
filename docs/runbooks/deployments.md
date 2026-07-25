# Zero-Downtime Deployments & Rollbacks

## Canary Releases
When releasing a new diagnostic algorithm or model integration, deploy behind a feature flag or a canary deployment.
1. Update `values.yaml` or `api-deployment.yaml` with the new image tag.
2. Set `enable_canary: true` in the ConfigMap/Secrets.
3. Observe the `CertificateVerificationFailures` alert in Grafana for 15 minutes.

## Rollback
If errors spike:
```bash
kubectl rollout undo deployment/driftguard-api
```

## Database Migrations
Always run Alembic migrations in a pre-hook or init-container.
> [!IMPORTANT]
> Never write destructive (drop column/table) migrations. Migrations must be strictly additive to ensure backward compatibility during a rollback.
