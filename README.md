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
The benchmark evidence is synthetic and currently does not support a causal-planner
performance advantage.

## License & Patents
**CONFIDENTIAL**. Do not distribute, publicly host, or present this software outside of cleared research circles. Patent novelty searches and formal IP filings are pending.
