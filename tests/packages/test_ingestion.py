import pytest
import uuid
from packages.ingestion.src.scanner import PIISecretScanner
from packages.ingestion.src.chunker import BaseChunker
from packages.contracts.src.models import ReplayStateManifest

def test_pii_scanner_rejects_secrets():
    scanner = PIISecretScanner()
    
    safe_text = "This is a document about machine learning."
    assert scanner.scan_text(safe_text) is False
    
    unsafe_text = "Here is my key: API_KEY=abc123XYZ"
    assert scanner.scan_text(unsafe_text) is True
    
    unsafe_text2 = "-----BEGIN PRIVATE KEY-----\nMIIEvgIB"
    assert scanner.scan_text(unsafe_text2) is True

def test_pii_scanner_rejects_pii():
    scanner = PIISecretScanner()
    unsafe_text = "My email is test@example.com and phone is 555-0199."
    assert scanner.scan_text(unsafe_text) is True

def test_chunker_determinism():
    chunker = BaseChunker(chunk_size=10, chunk_overlap=2)
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    chunks = chunker.chunk_text(text)
    
    # Check bounds
    assert chunks[0] == "one two three four five six seven eight nine ten"
    assert chunks[1] == "nine ten eleven twelve thirteen"

def test_replay_manifest_rejects_latest():
    # Should raise ValueError because of 'latest'
    with pytest.raises(ValueError, match="The 'latest' tag is forbidden"):
        manifest = ReplayStateManifest(
            run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            vector_index_snapshot_id="latest"
        )
