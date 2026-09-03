# Roadmap Implementation Audit: Removing Simulated/Fabricated Results

## Pre-Change Audit Findings

During our audit, we identified several areas where the repository was improperly fabricating success or hardcoding simulated utility within operational paths:

1. **`packages/replay/src/test_framework.py`**
   - **Previous logic:** `CanaryTestFramework.execute_canary` hardcoded `simulated_utility = 0.95`. `validate_quarantine` simply returned `True` for everything except "agent", fabricating quarantine confirmation.
   - **New logic:** `execute_canary` now explicitly returns `utility_observed=None`, removing the fabrication. `validate_quarantine` raises `NotImplementedError` preventing it from being used to fake production validation.

2. **`apps/api/src/services/recovery_pipeline.py`**
   - **Previous logic:** `EndToEndRecoveryPipeline` falsely labeled the certificate evidence as `RecoveryEvidenceKind.CONTROLLED_REPLAY` when it was actually using `CanaryTestFramework`.
   - **New logic:** Explicitly labels the certificate with `RecoveryEvidenceKind.SYNTHETIC_SIMULATION` when generating the recovery certificate. It also gracefully handles the `NotImplementedError` from test frameworks.

3. **`packages/recovery/src/orchestrator.py`**
   - **Previous logic:** The `IncidentMachine` blindly transitioned from `CANARY` status directly to `RECOVERED` with the message "Canary successful. Recovery deployed." without actual verification.
   - **New logic:** The machine now transitions to `RECOVERY_REJECTED` with an explicit message: "Real canary deployments are currently blocked pending production support. Refusing to fabricate recovery success."

4. **`packages/policy/src/transfer_guard.py`**
   - **Previous logic:** `TransferGuard` only checked the cryptographic signature and similarity scores, but allowed synthetic simulations to be transferred across boundaries.
   - **New logic:** `ProvenanceEnvelope` now carries the `evidence_kind`. The guard explicitly rejects the transfer if `evidence_kind == RecoveryEvidenceKind.SYNTHETIC_SIMULATION`.

## Evidence Propagation Changes
- Extended `ProvenanceEnvelope` in `transfer_guard.py` to include `evidence_kind`.
- Ensured tests in `test_recovery_pipeline.py` assert that `evidence_kind` is correctly propagated as `SYNTHETIC_SIMULATION` when using the mock framework.
- Ensured `test_transfer_guard.py` correctly verifies that `SYNTHETIC_SIMULATION` is rejected.


## Phase 2: Dynamic Replay and Generic Intervention Framework

1. **Removed Hard-coded Replay Query**
   - ReplayEngine now reconstructs the exact original run state from a ReplayStateManifest rather than executing a hard-coded or generic test query.
2. **Removed Retriever-only Assumption**
   - ReplayEngine now dynamically handles interventions over any ComponentType (e.g. GENERATOR, POLICY_CHECK, TOOL_CALL) rather than hardcoding retriever swaps.
3. **Introduced InterventionSpec**
   - Exposed InterventionSpec in ReplayCreateRequest enabling flexible intervention configurations.
   - Adjusted Pydantic models (e.g., ReplayEpisode, InterventionSpec) to ensure strict typing with enums (ComponentType, InterventionType) with proper coercions.

## Phase 3: Agent Tracing and Causal Execution Evidence (Prompt #9-#14)

1. **Pipeline Tracing Integration**
   - Connected the 7-agent pipeline (packages/rag_pipeline/src/agents.py) to the DriftGuardX TraceContext.
2. **Explicit Agent Execution Spans**
   - Emitted distinct SpanRecord spans using ComponentType.AGENT for every agent invocation (Orchestrator, Retrieval, Reasoning, Tool, Verifier, Policy, Response).
3. **Stable Identity and Version Metadata**
   - Populated identity fields into the ttributes of agent spans, including dgx.agent.id, dgx.agent.type, dgx.agent.version, dgx.model.provider, dgx.model.id, dgx.prompt.hash, dgx.config.hash, and dgx.tool_registry.hash.
4. **Causal Edge Tracking**
   - Established correct parent-child relationships where appropriate and added dgx.causal.source_span_id explicitly logging causal message passing.
5. **Memory Operation Linking**
   - Instrumented state-level memory reads (
ead_memory) and writes (write_memory) to generate their own MEMORY_READ and MEMORY_WRITE trace spans as children of the originating agent.
6. **Agent Decision Preservation**
   - Recorded internal agent decisions and provenance signals (e.g. dgx.decision.outcome = 'allow', dgx.evidence.classification = 'synthetic_simulation') in the span output.
