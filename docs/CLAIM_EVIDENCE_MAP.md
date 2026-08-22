# DriftGuard-X Patent Claim Evidence Map

| Patent Claim Element | Technical Implementation Evidence | Source Location |
| :--- | :--- | :--- |
| **Tamper-Evident Append-Only Ledger** | `verify_full_chain()` traverses deterministic canonical JSON hashes linking sequences to a genesis block. | `packages/ledger/src/store.py` |
| **Probabilistic RAEB Information Gain** | `RootCauseBeliefModel` updates $P(C_i | O)$ and calculates bounded Expected Entropy Reduction. | `packages/replay/src/belief_model.py` |
| **Cryptographic Transfer Boundaries** | `TransferGuard` verifies HMAC signatures on `ProvenanceEnvelope` before applying Jaccard similarity bounds. | `packages/policy/src/transfer_guard.py` |
| **Context Compaction Entailment Guard** | `SentenceTransformerNLIProvider` checks logical entailment (NLI) of claims to reject hallucinated summaries. | `packages/graph/src/compaction.py`, `packages/memory/src/entailment.py` |
| **Trusted Time Envelopes** | `TrustedTimeVerifier` forces temporal freshness checks to use cryptographically verified clock state, preventing replay attacks. | `packages/replay/src/time_authority.py`, `raeb.py` |
| **Atomic Execution Budgeting** | Multiprocessing subprocesses enforce `RLIMIT_AS` bounds while an `AtomicExecutionBudget` tracks lock-safe quotas. | `packages/replay/src/sandbox.py` |
| **Capability-Based Quarantine** | `ProvenanceMemoryStore` requires unforgeable `AccessContext` objects and logs tamper-evident audit trails. | `packages/memory/src/store.py`, `auth.py` |
| **Homoglyph / Spacing Defenses** | `secure_normalize` strips zero-width joiners, normalizes NFKC, maps confusables, and rejects BiDi overrides. | `packages/utils/src/unicode.py` |
