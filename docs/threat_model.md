# Threat Model (STRIDE)

This document covers the threat modeling of the DriftGuard-X architecture.

## Spoofing
- **Risk**: Trace spoofing, signature tampering.
- **Mitigation**: All `ReplayEpisode`s are structurally validated and bounded by cryptographic signatures via `LedgerChain`. Test `test_trace_spoofing` confirms tampered signatures are rejected.

## Tampering
- **Risk**: Modifying the Replay Sandbox or maliciously injecting tool outputs.
- **Mitigation**: Rationale and execution layers strictly sanitize JSON tool boundaries. Test `test_malicious_tool_output` explicitly tests and blocks malicious payload commands like `rm -rf`.

## Repudiation
- **Risk**: Denying that a recovery intervention was performed.
- **Mitigation**: The `cryptography` module enforces Ed25519 signatures, stored in an append-only sqlite chain. Repudiation is impossible without breaking the private key.

## Information Disclosure
- **Risk**: Leakage of tenant API keys or cross-tenant data.
- **Mitigation**: PII and secrets are scrubbed during redaction. Test `test_secret_leakage` confirms environment variables like `API_KEY` are stripped out. Test `test_privilege_escalation` asserts tenant isolation.

## Denial of Service (DoS)
- **Risk**: Replay attacks flooding the scheduler.
- **Mitigation**: Configurable budget caps (`budget_cap_usd`) and provider quotas ensure bounded financial and computational limits during chaos. 

## Elevation of Privilege
- **Risk**: SSRF or Path Traversal in the adapter fetch logic.
- **Mitigation**: Strict URL parsing and boundary validation. Test `test_ssrf_path_traversal` ensures local files cannot be fetched.
