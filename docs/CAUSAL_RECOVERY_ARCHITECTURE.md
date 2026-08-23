# DriftGuard-X: Causal Recovery Architecture

This document details the architectural components of the DriftGuard-X recovery engine.

## 1. Trace Capture & Graph Extraction
Every incident begins with AI execution traces being captured. The `GraphProvider` uses these traces to extract a causal graph representing the execution flow and dependencies between components (e.g., Memory, LLM, External API).

## 2. Replay Equivalence Envelope
When a failure target is registered (e.g., hallucination, schema violation), the `InterventionGenerator` proposes candidate solutions (rollback, swap). The `EnvelopeBuilder` then constructs a `ReplayEquivalenceEnvelope`. This envelope cryptographically isolates the minimum subset of the trace required to evaluate those candidates. Any state outside this envelope is mathematically proven to be irrelevant or functionally identical across replays.

## 3. Dynamic Causal Divergence Frontier & Exogenous-State Controller
During replay execution, the system monitors trace divergence. The `DivergenceFrontier` represents the strict boundary of allowed side-effects. The `Exogenous-State Controller` (part of the Divergence Validator) suppresses non-deterministic noise (e.g., timestamps) without violating causal constraints, ensuring validity. Any unexpected mutation immediately invalidates the causal evidence.

## 4. Sequential Causal Experiment Planner
Instead of exhausting all combinations, the `RiskLimitedSequentialCausalExperimentPlanner` iterates efficiently:
- Computes `ExpectedInformationGain` for each candidate.
- Selects the optimal replay experiment bounded by a `ResourceRiskPlanner` budget.
- Submits the experiment to the `ReplayExecutor`.

## 5. Evidentiary Stopping Rule & Belief Model
Following each replay, the `BeliefModel` performs Bayesian updates to the posterior probabilities of the root causes. The `StoppingPolicy` evaluates this belief state; once sufficient causal evidence distinguishes a clear recovery path, the loop halts, drastically saving tokens and GPU time.

## 6. Minimum Causal Recovery Cut
Once evidence is sufficient, the `RecoveryCutSolver` resolves the posterior belief state into an optimal recovery strategy. Formulated as a Weighted Hitting Set problem, it computes the smallest technically acceptable set of changes (the "cut") that disconnects the diagnosed failure-producing causal paths while preserving unaffected system behavior.

## 7. Preservation Invariants & Authorization
The computed cut undergoes strict validation via the `RecoveryValidator` to ensure subsystem isolation and invariant preservation. The `PolicyEngine` then performs cryptographic capability checks, ensuring no recovery executes without explicit authorization.

## 8. Causal Recovery Transportability Gate
After a successful canary deployment, the `Ledger` generates a causal evidence certificate. The `CausalTransportGate` uses this certificate and `CausalEnvironmentDescriptor` fingerprints to securely authorize cross-environment transports. This mechanism validates footprint dependencies against specific structural environment differences rather than relying on simplistic Jaccard similarity, automatically denying unauthorized cross-tenant transfers.
