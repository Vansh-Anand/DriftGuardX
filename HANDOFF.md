# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 13 — Hash-Chained Recovery Certificate Ledger and Independent Verification
**2. Estimated cumulative completion after verified gates:** 85%

**3. Repository audit and design decisions:**
The `packages/ledger` module introduces a cryptographic, append-only certificate chain. It separates hash integrity (SHA-256) from signer identity (Ed25519) as requested. The `LedgerChain` is backed by `aiosqlite` for persistence. A `DevelopmentSigner` provides local runnable signing while `KMSProviderSigner` defines the stub for production hardware keys. `RecoveryCertificate` uses deterministic JSON serialization (with domain separators and versioning) to ensure cross-platform hash stability. The exporter provides both full machine bundles (for cryptographic verification) and redacted views (for human analysis). A standalone CLI (`apps/cli/verifier.py`) operates independently from the database to prove ledger integrity externally.

**4. Files created, modified, migrated, or deprecated:**
- `packages/ledger/src/crypto.py` (New: SignerProtocol, DevelopmentSigner, KMSProviderSigner, verify_signature)
- `packages/ledger/src/schema.py` (New: RecoveryCertificate, deterministic canonical_bytes)
- `packages/ledger/src/chain.py` (New: LedgerChain via aiosqlite, append_certificate, verify_chain)
- `packages/ledger/src/export.py` (New: JSON bundle and redacted human export logic)
- `apps/cli/verifier.py` (New: Standalone cryptographic bundle verifier)
- `apps/web/app/ledger/page.tsx` (New: Ledger UI dashboard)
- `tests/e2e/test_ledger_tamper.py` (New: Tamper detection and latency benchmarks)
- `requirements-dev.txt` (Modified: Added `cryptography` package)
- `CHANGELOG.md` (Modified: Added v0.13.0)

**5. Commands executed and exact test/results summary:**
```
$env:PYTHONPATH="."; python -m pytest tests/e2e/test_ledger_tamper.py -v -s
8 passed, 1 warning in 3.03s

Tests:
  test_clean_chain_verifies                       PASSED
  test_tamper_alter_content                       PASSED
  test_tamper_alter_previous_hash                 PASSED
  test_tamper_delete_historical_row               PASSED
  test_invalid_signature_on_append                PASSED
  test_wrong_key_signature_rejected               PASSED
  test_export_redaction                           PASSED
  test_latency_scaling_benchmark                  PASSED

Benchmarks:
  [BENCHMARK] Appended 100 certs in 1.877s (Avg 18.77ms/cert)
  [BENCHMARK] Verified 100 certs in 0.049s (Avg 0.49ms/cert)
```

**6. Demonstration or experiment artifacts with paths:**
- `apps/cli/verifier.py` — Portable verification tool.
- `apps/web/app/ledger/page.tsx` — Dashboard UI rendering the certificate chain.

**7. Security, privacy, safety, and IP-disclosure checks:**
- Privacy: The `export_human_summary` function correctly redacts `prompt` and `secret` keywords from the intervention vector to prevent PII/secret leaks in human reporting.
- Integrity: Signatures are computed over the unredacted canonical bytes. Any content alteration (including redacting fields) correctly invalidates the signature unless verified using the exact machine export bundle.
- Anti-Tamper: Missing rows, altered previous hashes, and invalid signatures are all caught by `verify_chain`.
- Identity: Development keys are explicitly segregated from KMS providers.

**8. Known limitations and failed/negative results:**
- While the application layer enforces append-only rules, strict database-level append-only enforcement (e.g., SQLite `BEFORE UPDATE` / `BEFORE DELETE` triggers) is recommended for production deployments but not included in this development scaffold.

**9. Data migrations and rollback notes:**
- The `aiosqlite` backend creates the `ledger` table via `LedgerChain.initialize()`. If the schema evolves in later prompts, Alembic migrations will be needed.

**10. HANDOFF.md updated; next prompt:** 14
