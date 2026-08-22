# DriftGuard-X Threat Model

## 1. System Assets
- **Provenance Memory**: Historical trace data, user partitions, and forensic audit logs.
- **Transparency Ledger**: Cryptographically verifiable sequence of run artifacts.
- **Execution Sandbox**: Restricted compute environment for do-operator replay validation.
- **Provider Beacons**: Semantic baselines detecting silent shifts in upstream models.

## 2. Threat Actors
- **Malicious Tenant**: Attempts cross-tenant data access or isolation escape.
- **Compromised Hosted Provider**: Silently shifts behavior or returns malicious inputs.
- **Insider Threat / Rogue Auditor**: Attempts to read quarantined data without capability authorization or mutates historical ledgers.

## 3. Attack Vectors & Mitigations
### 3.1 Ledger Mutation (Hash-Chain Spoofing)
- **Threat**: An attacker modifies an old SQLite row to remove evidence of drift.
- **Mitigation**: `verify_full_chain` enforces sequential `previous_entry_hash` linkage and canonical `payload_hash` matching. Genesis validation prevents chain truncation.

### 3.2 Quarantine Bypass
- **Threat**: An attacker reads restricted partitions using a forged `forensic_auditor` role string.
- **Mitigation**: `ProvenanceMemoryStore` requires a cryptographically validated `AccessContext` containing explicit, bounded `capability_ids`. Audit logs securely hash all access attempts.

### 3.3 Semantic Camouflage
- **Threat**: An LLM provider changes formatting to bypass heuristic checks (e.g. `b.a.d.w.o.r.d` or zero-width joiners).
- **Mitigation**: `utils.unicode.secure_normalize` strips zero-width chars, maps homoglyphs, and removes punctuation before constraint checks.

### 3.4 Sandbox Escape (DoS & RCE)
- **Threat**: A replayed agent executes shell commands or allocates infinite memory.
- **Mitigation**: OS-level `RLIMIT_AS` and `RLIMIT_CPU` enforce strict bounds. `sys.addaudithook` blocks network sockets and shell subprocesses synchronously.

### 3.5 Provenance Forgery (Cross-Tenant Transfer)
- **Threat**: Attacker spoofs a TransferGuard envelope to apply untrusted diagnoses.
- **Mitigation**: `TransferGuard` requires a cryptographically signed `ProvenanceEnvelope` encompassing the environment hash and calibration bounds.
