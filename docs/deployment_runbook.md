# DriftGuard-X Production Deployment Runbook

## Prerequisites

1. **Kubernetes Cluster**: Version 1.25+ with NetworkPolicy controller (e.g., Calico or Cilium) enabled.
2. **Prometheus Operator**: Installed and configured to scrape `ServiceMonitors` and evaluate `PrometheusRules`.
3. **Registry Access**: Permissions to pull immutable digests from `ghcr.io/driftguardx/*`.
4. **Secrets**: A pre-provisioned `driftguard-secrets` secret containing `POSTGRES_PASSWORD` and `REDIS_PASSWORD`.

## Deployment Sequence

1. **Apply Namespace and Secrets**
   Ensure the `driftguard-secrets` Kubernetes Secret is applied before any workloads.
   
2. **Apply Network Policies**
   ```bash
   kubectl apply -f deploy/k8s/network-policies.yaml
   ```
   *Verify that policies are active using a test pod to check egress blocks.*

3. **Deploy Stateful Services (Postgres & Redis)**
   ```bash
   kubectl apply -f deploy/k8s/postgres.yaml
   kubectl apply -f deploy/k8s/redis.yaml
   ```
   *Wait for pods to reach `Running` state.*

4. **Run Database Migrations**
   ```bash
   kubectl apply -f deploy/k8s/migration-job.yaml
   ```
   *Check logs of the migration job to ensure `alembic upgrade head` completed successfully.*

5. **Deploy API and Worker**
   ```bash
   kubectl apply -f deploy/k8s/api-deployment.yaml
   kubectl apply -f deploy/k8s/worker-deployment.yaml
   ```

6. **Deploy Web Interface**
   ```bash
   kubectl apply -f deploy/k8s/web-deployment.yaml
   ```

7. **Apply Observability Rules**
   ```bash
   kubectl apply -f deploy/k8s/observability/prometheus-rules.yaml
   ```

## Troubleshooting

### API Pod Failing Liveness/Readiness Probes
- Check `kubectl describe pod <api-pod>`. If it's failing because it cannot reach the DB, check the `NetworkPolicy` logs or ensure the migration job succeeded.

### Worker Network Timeouts
- If the worker cannot reach external providers (e.g., OpenAI), ensure `allow-external-egress` network policy is correctly applied and covers the worker's labels.

### Alert: CertificateVerificationFailures
- If this alert fires, an intervention or replay signature verification failed. Check the API logs for `InvalidSignature` or `ExpiredCertificate`. Rotate keys if necessary.
