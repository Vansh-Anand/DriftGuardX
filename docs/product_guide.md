# DriftGuard-X Product Guide

## Quickstart
1. **Prerequisites**: Python 3.12+, Node.js 20+, Docker (Optional).
2. **Install**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements-dev.txt
   npm install --prefix apps/web
   ```
3. **Run Environment**:
   ```bash
   uvicorn apps.api.src.main:app --reload &
   npm run dev --prefix apps/web
   ```

## Private Deployment Guide
For Kubernetes-based isolation, use the provided `deploy/k8s` manifests.
```bash
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/web-deployment.yaml
```
*Note: This architecture assumes strict tenancy mapping via OIDC.*

## User Roles
- **Operator**: Can view traces and dashboards. Cannot approve rollbacks.
- **Admin / BU Manager**: Can approve Level 2 Policies and view raw audit logs.
- **Security Principal**: Has break-glass approval for CRITICAL policies.

## Certificate Verification Guide
If you receive a `.json` recovery bundle, verify its integrity without needing the main database:
```bash
python apps/cli/verifier.py --bundle /path/to/bundle.json
```
This validates the cryptographic Ed25519 signature and the hash-chain linkage to ensure the recovery artifact was not tampered with.

## Replay and Recovery Guide
1. Identify drifted run via the **Diagnosis Dashboard**.
2. Run the **BCRB Scheduler** to isolate the optimal counterfactual intervention.
3. Review the **Policy Queue**.
4. Once approved, the **Recovery Engine** executes the rollback and emits a cryptographic certificate.
