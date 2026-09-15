# DriftGuard-X TRL5 Readiness Check

Updated: 2026-09-15

This document records the local evidence for treating DriftGuard-X as a
TRL5-candidate research prototype: validated components integrated in a
relevant local research environment. It does not claim production readiness,
field deployment, legal patentability, or safety certification.

## TRL5 Interpretation

For this project, TRL5 means the integrated system can run representative
agentic-RAG reliability workflows in a controlled local environment with
evidence that failures are bounded, classified, or refused rather than silently
treated as successful production recovery.

## Activity Matrix

| Activity | Local evidence | TRL5 status | Remaining external gate |
|---|---|---|---|
| API health and readiness | Live Uvicorn service returned `/health` and `/ready` OK on loopback SQLite. | Pass | Hosted CI and staging health checks against PostgreSQL. |
| Authentication boundary | Anonymous providers/runs requests returned 401; mock-token requests succeeded. | Pass for local mode | OIDC tenant integration and IdP-backed role validation. |
| Run execution | Live `POST /v1/runs` synthetic request completed with reliability score and 9 trace spans. | Pass for local synthetic mode | Real provider and production workload validation. |
| Trace retrieval | Live `GET /v1/runs/{id}/trace` returned the generated trace. | Pass | External workload trace capture and retention exercise. |
| Provider registry | Live `/v1/providers/` returned configured provider metadata under auth. | Pass for local registry | Real provider credential validation and rate-limit handling. |
| Replay admission control | Full tests include durable receipts, atomic claim, expiry, mismatch refusal, audit chain, worker boundary, and replay API checks. | Pass for local SQLite contention | Shared transactional backend and multi-host worker-loss stress. |
| Recovery and rollback | Unit, integration, and E2E suites cover policy-gated recovery, rollback, canary paths, and refusal states. | Pass for controlled/local fixtures | Controlled canary against real workload and managed signing keys. |
| Graph and diagnosis | Full suite covers graph construction, validation, diffusion, BCRB, GAT compatibility, and insufficient-evidence behavior. | Pass for local controlled scenarios | Broader real fault-family experiments and independent replication. |
| Evidence integrity | Security/E2E tests cover ledger tamper, manifest integrity, evidence classification, and mutation refusal. | Pass | External witness/KMS or managed key validation. |
| Web console | Production build and Playwright E2E passed. | Pass | Deployed environment smoke with configured API origin and auth. |
| Real-time TRL UI | Landing and dashboard now show TRL status, live smoke evidence, controlled replay evidence, and benchmark boundaries. Desktop/mobile screenshots were captured under `output/ui/`. | Pass for local console UX | Hosted preview review and staging API-connected UI smoke. |
| Resilience/performance | Resilience/performance test group passed. | Pass for simulated local stress | Load, chaos, backup, and restore drills on target infrastructure. |
| Controlled replay evidence | Existing multi-dataset controlled replay artifacts are hash/protocol verified; Makefile benchmark target now runs and verifies SciFact evidence. | Partial pass | Clean-source rerun in hosted CI or second clean machine. |
| Packaging/reproducibility | Package/database tests passed; `verify-local` and `run-benchmarks` targets are defined. | Partial pass | GNU Make unavailable on this Windows host; second clean environment required. |

## Verification Snapshot

Commands run locally on 2026-09-15:

- `python -m pytest tests -q`: 610 passed, 22 skipped, 7 warnings.
- `npm --prefix apps/web run build`: passed.
- `npm --prefix apps/web run test:e2e`: 5 passed.
- `python -m ruff check apps packages tests`: passed.
- `python scripts/verify_controlled_evidence.py ...`: verified 7 controlled evidence files.
- Live API smoke:
  - `/health`: OK.
  - `/ready`: OK with database check.
  - anonymous `/v1/providers/` and `/v1/runs`: 401 as expected.
  - authenticated `/v1/providers/`: OK.
  - authenticated `/v1/runs`: OK.
  - authenticated synthetic `POST /v1/runs`: completed.
  - authenticated `GET /v1/runs/{id}/trace`: returned 9 spans.
- Visual UI smoke:
  - `output/ui/trl-ui-landing-desktop.png`
  - `output/ui/trl-ui-landing-mobile.png`
  - `output/ui/trl-ui-dashboard-authenticated.png`

## Current TRL Judgment

The project is a defensible TRL5 candidate for a local research/demo
environment because the integrated API, worker-facing admission logic, recovery
logic, evidence integrity checks, controlled benchmark harness, and web console
all run together under local verification.

It is not yet a TRL6 or production-ready system. A stronger readiness claim
requires hosted CI for the exact pushed revision, PostgreSQL/Redis-backed
staging smoke, clean-machine reproduction, shared backend receipt stress,
managed-key evidence signing, external red-team review, and real workload
validation.
