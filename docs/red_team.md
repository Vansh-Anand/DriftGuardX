# Red Team & Limitations Report

## Unresolved Risks
- **In-Memory MLflow limit**: Currently, evaluation orchestration operates on a local SQLite `mlruns.db`. While secure for local operation, a multi-tenant cloud environment requires migrating to a hosted tracking server with RBAC.
- **Provider Outages**: Chaos test `test_provider_timeout` confirms the system falls back gracefully to templates. However, prolonged provider unavailability effectively disables generative diagnostic rationales.
- **Cryptographic Bottleneck**: Current Ed25519 signing incurs a p99 latency overhead of 5.0 seconds under 50-cert concurrent load. For extreme scale, batch signing or hardware acceleration (KMS) is needed.

## Production Blockers
- **Patent Strategy**: We are maintaining a closed-source profile until patent strategy finalizes. No screenshots, novelty claims, or datasets should leak outside the repository.
- **Adapter Egress**: We must enforce network-level egress restrictions via Istio/Envoy so that malicious tool payloads (even if caught by our code) are blackholed at the OS network level.

## Assumptions
- We assume that the `ReplayEpisode` contract remains the strict perimeter. Any unstructured injection that avoids Pydantic validation compromises the system.
