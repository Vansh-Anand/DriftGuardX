# DriftGuard-X 
*v2.0.0-rc.1 - Internal Research Prototype*

> [!WARNING]
> **Not for Production Use**. This is an internal research prototype designed for evaluating causal inference in agentic pipelines. It does **not** provide guaranteed causality, absolute safety, legal certification, or production readiness. Any mathematical bounds documented herein apply strictly to the evaluated synthetic models and do not serve as an unconditional safety guarantee.

## Overview
DriftGuard-X is an experimental framework for evaluating Budget-Constrained Counterfactual Replay in multi-agent pipelines. It intercepts pipeline traces, models them as causal graphs, and attempts to bound diagnostic costs when identifying cross-layer semantic drift.

## Key Mechanisms (Experimental)
1. **Trace Fabric**: Intercepts execution spans to build a deterministic provenance graph.
2. **Diffusion Propagation**: Maps symptomatic drift backwards via analytical topological scoring.
3. **Budget-Constrained Bandit (BCRB)**: Estimates optimal counterfactual interventions to limit compute waste during diagnosis.
4. **Policy-Gated Recovery**: A hierarchical policy engine governing mock recovery actions and issuing cryptographic ledgers (Ed25519) of the rollback state.

## Setup and verification

For a local Windows research console, install the dependencies below and run:

```powershell
uv sync --frozen --extra dev --extra infra
npm --prefix apps/web ci
./scripts/start-local.ps1
```

Open http://127.0.0.1:3010/runs and use **Sign In** with a local demo email.
The API runs at http://127.0.0.1:8010. The launcher uses local mock authentication
and stores its SQLite database and logs in `.local-runtime/`. It starts hidden
background processes and prints their process IDs. Choose alternate ports with
`-ApiPort` and `-WebPort` when needed. This mode is a local research demonstration;
real provider execution and production recovery require their own configuration.

Use Python 3.11 or 3.12 (Python 3.13 is not supported by this release):

```bash
uv sync --frozen --extra dev --extra infra
DGX_MODE=test DGX_CAPABILITY_SECRET=local-test-secret DGX_TRANSPORT_KEY=local-transport-key \
  uv run pytest tests/unit tests/security tests/contract tests/integration -m "not slow"
```

The committed `uv.lock` resolves the project for Python 3.11–3.12; `requirements.lock` is a hash-verified export for the runtime, dev, and infrastructure dependencies. Refresh both with `make lock` and verify them with `make lock-check`.

The web application is a research UI and is intentionally labelled where it
shows synthetic demonstration data. Synthetic replay evidence is not evidence
of production recovery: a production canary requires a controlled replay and
the corresponding capability-gated approval path.

For Docker deployment, configure OIDC (`AUTH_MODE=oidc`, issuer, audience, and
JWKS URI). Mock authentication is deliberately rejected in staging/production.

Release-candidate verification and benchmark limitations are recorded in
[`releases/2.0.0-rc.1/RELEASE_EVIDENCE.md`](releases/2.0.0-rc.1/RELEASE_EVIDENCE.md).
The original causal-planner benchmark remains synthetic and does not support a
general causal-planner performance advantage. A separate hash-bound SciFact/BM25
benchmark executes real public dataset records under controlled index fault
injection and is explicitly classified as `controlled_replay`, not production
evidence. Run it with:

```bash
uv run python scripts/download_scifact.py
uv run python -m apps.cli.run_controlled_replay_benchmark --max-queries 100
```

## License & Patents
**CONFIDENTIAL**. Do not distribute, publicly host, or present this software outside of cleared research circles. Patent novelty searches and formal IP filings are pending.
