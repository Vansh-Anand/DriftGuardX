# Operational Incident Runbook

## Overview
This runbook covers critical operational failure paths inside the DriftGuard-X evaluation loop.

## 1. Trace Ingestion Failures
**Symptoms**: Traces dropped, `/v1/runs` returning 503, Ingestion Lag spiked.
**Action**: 
- Verify PostgreSQL connectivity.
- Verify Redis queue for the `job_orchestrator`.
- Check JWT tenant scopes for authorization misconfiguration.

## 2. Replay Engine Timeouts
**Symptoms**: Bandit scheduler stuck in EXPLORE state; exhaustive benchmark loops failing.
**Action**:
- Replay relies on deterministic local mock providers (by default). If using an external LLM adapter (OpenAI/Anthropic), verify API keys and network routing.
- Check the sandbox auditing hooks: Replays making unexpected network or file system calls are intentionally killed by the security overlay.

## 3. Cryptographic Verification Failures
**Symptoms**: `/v1/recovery/execute` succeeds, but `apps/cli/verifier.py` rejects the certificate.
**Action**:
- The Ed25519 hash chain has forked or lost a link.
- Do NOT bypass verification. A failed certificate implies the database state and the authorized policy state are desynchronized. Manually audit the `policy_audit_logs` table.

## 4. Disaster Recovery
For full platform DR steps, see `docs/runbooks/disaster_recovery.md`.
