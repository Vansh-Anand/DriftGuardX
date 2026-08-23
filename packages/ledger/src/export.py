"""
DriftGuard-X v2 — Ledger Exporter
PRIVATE — All Rights Reserved.

Exports certificates in JSON format or machine verification bundles.
Redacts sensitive content from the intervention vector while retaining hashes.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from packages.ledger.src.schema import RecoveryCertificate


def redact_sensitive_data(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Redact specific fields that might contain PII or sensitive prompts,
    while leaving structural integrity intact. Note: Redaction happens on the
    exported view; the signature still covers the unredacted canonical bytes!
    Wait, if we redact data, the verification of the signature on the exported bundle will FAIL.
    Therefore, a machine verification bundle MUST contain the exact bytes that were signed.
    If privacy is required, the original certificate should only store hashes of sensitive
    data, which we enforce at creation time. The export must NOT modify fields if it 
    expects the signature to remain valid.

    We provide two exports:
    1. `machine_bundle`: Exact unredacted JSON required for cryptographic verification.
    2. `human_summary`: Redacted/simplified view for PDFs or dashboards.
    """
    summary = payload.copy()

    # Redact sensitive values from the intervention vector for human summaries
    if "intervention_vector" in summary:
        safe_vector = {}
        for k, v in summary["intervention_vector"].items():
            if "prompt" in k.lower() or "secret" in k.lower() or "key" in k.lower():
                safe_vector[k] = "[REDACTED]"
            else:
                safe_vector[k] = v
        summary["intervention_vector"] = safe_vector

    return summary


def export_machine_bundle(certs: list[RecoveryCertificate]) -> str:
    """
    Exports a complete, unredacted JSON bundle of certificates suitable for 
    independent cryptographic verification by the standalone verifier.
    """
    bundle = {
        "version": "1.0",
        "type": "DriftGuardX_Ledger_Verification_Bundle",
        "certificates": [asdict(c) for c in certs]
    }
    return json.dumps(bundle, indent=2)


def export_human_summary(certs: list[RecoveryCertificate]) -> str:
    """
    Exports a redacted JSON summary for human review/reporting.
    Signatures will NOT verify against this output.
    """
    summaries = []
    for c in certs:
        summaries.append(redact_sensitive_data(asdict(c)))

    bundle = {
        "version": "1.0",
        "type": "DriftGuardX_Ledger_Human_Summary",
        "notice": "Signatures will not verify against this redacted payload.",
        "certificates": summaries
    }
    return json.dumps(bundle, indent=2)
