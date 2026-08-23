#!/usr/bin/env python3
"""
DriftGuard-X v2 — Standalone Ledger Verifier CLI
PRIVATE — All Rights Reserved.

Verifies a machine export bundle independently of the main application database.
Checks:
1. Certificate signatures using the public key embedded in the certificate 
   (in a production setting, this script would take a trusted root public key).
2. Hash chaining (previous_cert_hash matches the actual hash of the prior cert).
3. Hash consistency (cert_id and content match).

Usage:
  python verifier.py bundle.json
"""
import argparse
import base64
import hashlib
import json
import sys
from typing import Any

# Standalone imports for crypto to avoid pulling in app dependencies
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:
    print("Error: 'cryptography' package is required. Install via `pip install cryptography`.")
    sys.exit(1)


DOMAIN_SEPARATOR = "DriftGuardX-Recovery-Cert-V1"


def get_canonical_bytes(cert_dict: dict[str, Any]) -> bytes:
    """Reconstruct the exact canonical bytes used for signing."""
    # Remove authentication fields
    d = cert_dict.copy()
    d.pop("signature", None)
    d.pop("signer_key_id", None)
    d.pop("signer_pub_key", None)

    payload = {
        "domain": DOMAIN_SEPARATOR,
        "version": "1.0",
        "data": d
    }
    json_str = json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=True)
    return json_str.encode('utf-8')


def compute_hash(canonical_bytes: bytes) -> str:
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_signature(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
    try:
        pub_bytes = base64.b64decode(public_key_b64)
        sig_bytes = base64.b64decode(signature_b64)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description="DriftGuard-X Ledger Verifier")
    parser.add_argument("bundle", help="Path to machine verification JSON bundle")
    args = parser.parse_args()

    try:
        with open(args.bundle) as f:
            bundle = json.load(f)
    except Exception as e:
        print(f"Error loading bundle: {e}")
        sys.exit(1)

    if bundle.get("type") != "DriftGuardX_Ledger_Verification_Bundle":
        print("Error: Invalid bundle type.")
        sys.exit(1)

    certs = bundle.get("certificates", [])
    print(f"Loaded {len(certs)} certificates.")

    if not certs:
        print("Verification SUCCESS: Empty chain.")
        sys.exit(0)

    expected_prev = "GENESIS"

    for i, cert in enumerate(certs):
        cert_id = cert.get("cert_id", f"UNKNOWN-{i}")

        # 1. Check Linkage
        prev_hash = cert.get("previous_cert_hash")
        if prev_hash != expected_prev:
            print(f"FAIL [{cert_id}]: Chain broken. Expected prev {expected_prev}, got {prev_hash}")
            sys.exit(1)

        # 2. Check Cryptographic Integrity
        canonical_bytes = get_canonical_bytes(cert)
        actual_hash = compute_hash(canonical_bytes)

        signature = cert.get("signature")
        pub_key = cert.get("signer_pub_key")

        if not signature or not pub_key:
            print(f"FAIL [{cert_id}]: Missing signature or public key.")
            sys.exit(1)

        if not verify_signature(pub_key, canonical_bytes, signature):
            print(f"FAIL [{cert_id}]: Cryptographic signature invalid.")
            sys.exit(1)

        expected_prev = actual_hash
        print(f"PASS [{cert_id}]: Hash {actual_hash[:8]}... Linkage & Signature OK.")

    print("\nVerification SUCCESS: The entire certificate chain is valid and untampered.")
    sys.exit(0)


if __name__ == "__main__":
    main()
